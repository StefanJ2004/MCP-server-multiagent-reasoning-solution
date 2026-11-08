"""Multi-agent: planer -> paralelni istrazivaci -> sintetizator, bez frameworka.

    pitanje
      -> PLANER        1 poziv modela, bez alata, vraca JSON sa podzadacima (jedan po kompaniji)
      -> ISTRAZIVACI   svaki podzadatak = nasa petlja run_agent iz faze 2, sa SVOJIM kratkim kontekstom;
                       rade paralelno (asyncio.gather), najvise MAX_PARALLEL_RESEARCHERS odjednom
      -> SINTETIZATOR  1 poziv modela, bez alata; pise odgovor ISKLJUCIVO iz nalaza istrazivaca

Isti model, isti alati i ista podesavanja kao jedan agent (fer poredjenje u evalu).
Svi agenti dele JEDNU MCP vezu; MCP razlikuje istovremene zahteve po ID-u.

Pokretanje:
  python -m agents.multi_agent --id C4
  python -m agents.multi_agent "Compare revenue of NVDA and AMD in FY2024."
"""
import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from mcp import Client, StdioServerParameters
from openai import AsyncOpenAI

from agents.single_agent import (LLM_TIMEOUT_SECONDS, MAX_OUTPUT_TOKENS, SYSTEM_PROMPT, AgentResult,
                                 _question_from_eval, provider_options, run_agent)

ROOT = Path(__file__).resolve().parent.parent

MAX_PARALLEL_RESEARCHERS = 6   # vise istovremenih poziva = brze, ali i vise sansi za limit provajdera
MAX_SUBTASKS = 20              # 13. eval pitanje ima 18 kompanija
PLAN_ATTEMPTS = 2              # planer dobija jos jednu sansu ako vrati neispravan JSON

PLANNER_PROMPT = """You are the planner of a financial research team. Split the user's question into \
independent research subtasks. Each subtask goes to a separate researcher who has tools for annual \
financial numbers (get_financials) and 10-K report text search (search_filing), one company at a time.

Rules:
- Create one subtask per company. If the question needs both numbers and explanations for a company, \
put both in that company's subtask.
- Each subtask must be self-contained: the company ticker, the fiscal years, and exactly what to find \
(which metrics and/or what to explain). Researchers do not see the other subtasks.
- fiscal_year is the calendar year in which the fiscal year ENDS.
- If a company in the question is not in the list below, still create a subtask for it; the researcher \
will report that the data is unavailable.
- Do not answer the question and do not compare companies yourself. A separate writer will combine \
the researchers' findings.

Respond with JSON only, in exactly this format:
{{"subtasks": [{{"id": "t1", "task": "..."}}, {{"id": "t2", "task": "..."}}]}}

Companies covered by the tools:
{companies}"""

# Istrazivac ima ista pravila kao jedan agent (fer poredjenje) + uputstvo da radi samo svoj deo.
RESEARCHER_PROMPT = SYSTEM_PROMPT + """

You are one researcher in a team. Do ONLY your subtask. The original question is given only as \
context: do not research other companies. Report your findings concisely with exact numbers, \
fiscal periods and citations. Another agent writes the final answer from your findings."""

SYNTHESIZER_PROMPT = """You write the final answer to the user's question using ONLY the researchers' \
findings below. Do not use outside knowledge and never invent numbers.

Rules:
- Keep the citations from the findings (source_id or passage_id in brackets) after every number and claim.
- If a researcher found no result, say which data is missing instead of guessing.
- If the question has a false premise, correct it using the findings.
- Answer the question directly and briefly."""


@dataclass
class MultiAgentResult:
    answer: str | None
    stop_reason: str                                   # answer | output_cut | empty_answer | razlog sa API-ja
    plan: list[dict] = field(default_factory=list)
    plan_fallback: bool = False                        # True = planer nije uspeo, ceo zadatak je isao 1 istrazivacu
    findings: list[dict] = field(default_factory=list)
    llm_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    max_input_tokens: int = 0                          # najduzi pojedinacni prompt bilo kog agenta
    research_seconds: float = 0.0                      # trajanje faze istrazivaca (paralelno)
    seconds: float = 0.0


def _print_event(event: str, agent: str = "", **data) -> None:
    print(f"[{agent}] [{event}] " + " ".join(f"{k}={v}" for k, v in data.items()), flush=True)


async def _companies_for_prompt(mcp) -> str:
    """Spisak kompanija za planera: jedan poziv alata na pocetku, umesto da planer ima alate."""
    result = await mcp.call_tool("list_companies", {})
    companies = json.loads(result.content[0].text)["companies"]
    return "\n".join(
        f"- {c['ticker']}: {c['name']}, {c['sector']}, fiscal year ends {c['fiscal_year_ends']}, "
        f"fiscal years {min(c['fiscal_years_available'])}-{max(c['fiscal_years_available'])}"
        for c in companies)


def parse_plan(text: str | None) -> list[dict]:
    """Proverava JSON plana. Baca ValueError sa porukom koju planer dobija nazad da se ispravi."""
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON ({e})")
    subtasks = data.get("subtasks") if isinstance(data, dict) else None
    if not isinstance(subtasks, list) or not subtasks:
        raise ValueError('expected a non-empty list under the key "subtasks"')
    plan = []
    for i, item in enumerate(subtasks[:MAX_SUBTASKS], start=1):
        task = item.get("task") if isinstance(item, dict) else None
        if not isinstance(task, str) or not task.strip():
            raise ValueError(f'subtask {i} has no "task" text')
        plan.append({"id": f"t{i}", "task": task.strip()})   # ID-eve dodeljujemo mi, da budu jedinstveni
    return plan


class _Usage:
    """Sabira pozive i tokene svih agenata: toliko kosta jedno pitanje."""
    def __init__(self):
        self.llm_calls = self.input_tokens = self.output_tokens = self.max_input_tokens = 0

    def add(self, usage):
        self.llm_calls += 1
        self.input_tokens += usage.prompt_tokens
        self.output_tokens += usage.completion_tokens
        self.max_input_tokens = max(self.max_input_tokens, usage.prompt_tokens)


async def _complete(llm, model, messages, extra_body, usage: _Usage, on_event, agent: str, **kwargs):
    """Jedan poziv modela bez alata (planer, sintetizator)."""
    t0 = time.perf_counter()
    response = await llm.chat.completions.create(
        model=model, messages=messages, max_tokens=MAX_OUTPUT_TOKENS, temperature=0,
        extra_body=extra_body or {}, **kwargs)
    choice = response.choices[0]
    usage.add(response.usage)
    on_event("model", agent=agent, seconds=round(time.perf_counter() - t0, 1),
             input_tokens=response.usage.prompt_tokens, output_tokens=response.usage.completion_tokens,
             finish=choice.finish_reason)
    return choice


async def make_plan(question, llm, mcp, model, extra_body, usage, on_event) -> tuple[list[dict], bool]:
    """Vraca (plan, fallback). Neispravan plan -> planer dobija gresku i jos jednu sansu;
    ako ni tada ne uspe, ceo zadatak ide jednom istrazivacu (sistem ne pada zbog loseg plana)."""
    messages = [{"role": "system", "content": PLANNER_PROMPT.format(companies=await _companies_for_prompt(mcp))},
                {"role": "user", "content": question}]
    for attempt in range(1, PLAN_ATTEMPTS + 1):
        choice = await _complete(llm, model, messages, extra_body, usage, on_event, "planner",
                                 response_format={"type": "json_object"})
        try:
            if choice.finish_reason != "stop":
                raise ValueError(f"response was not finished (finish_reason={choice.finish_reason})")
            plan = parse_plan(choice.message.content)
            on_event("plan", agent="planner", subtasks=len(plan))
            return plan, False
        except ValueError as e:
            on_event("plan_error", agent="planner", attempt=attempt, error=e)
            messages += [{"role": "assistant", "content": choice.message.content or ""},
                         {"role": "user", "content": f"Your plan is invalid: {e}. Respond with JSON only, "
                                                     "in the required format."}]
    return [{"id": "t1", "task": question}], True


async def research(subtask, question, llm, mcp, model, extra_body, semaphore, on_event) -> AgentResult:
    """Jedan istrazivac = petlja iz faze 2 sa svojim promptom i svojim kratkim kontekstom."""
    agent = f"researcher:{subtask['id']}"
    async with semaphore:                              # najvise N istrazivaca istovremeno
        on_event("start", agent=agent, task=subtask["task"])
        try:
            return await run_agent(
                f"Subtask: {subtask['task']}\n\nOriginal question (context only): {question}",
                llm, mcp, model, extra_body=extra_body, system_prompt=RESEARCHER_PROMPT,
                on_event=lambda event, **data: on_event(event, agent=agent, **data))
        except Exception as e:                         # pad jednog istrazivaca ne obara ostale
            on_event("error", agent=agent, error=repr(e))
            return AgentResult(answer=None, stop_reason=f"error: {e}")


def _findings_text(question: str, plan: list[dict], results: list[AgentResult]) -> str:
    parts = [f"Question: {question}\n\nResearchers' findings:"]
    for subtask, r in zip(plan, results):
        body = r.answer if r.stop_reason == "answer" else f"NO RESULT (researcher stopped: {r.stop_reason})"
        parts.append(f"### {subtask['id']}: {subtask['task']}\n{body}")
    return "\n\n".join(parts)


async def run_multi_agent(question: str, llm, mcp, model: str, extra_body: dict | None = None,
                          max_parallel: int = MAX_PARALLEL_RESEARCHERS,
                          on_event: Callable = _print_event) -> MultiAgentResult:
    started = time.perf_counter()
    usage = _Usage()

    # 1. planer
    plan, fallback = await make_plan(question, llm, mcp, model, extra_body, usage, on_event)

    # 2. istrazivaci, paralelno. gather vraca rezultate istim redom kao plan.
    semaphore = asyncio.Semaphore(max_parallel)
    research_started = time.perf_counter()
    results = await asyncio.gather(*(
        research(s, question, llm, mcp, model, extra_body, semaphore, on_event) for s in plan))
    research_seconds = round(time.perf_counter() - research_started, 1)
    for r in results:
        usage.llm_calls += r.steps
        usage.input_tokens += r.input_tokens
        usage.output_tokens += r.output_tokens
        usage.max_input_tokens = max(usage.max_input_tokens, r.max_input_tokens)

    # 3. sintetizator
    messages = [{"role": "system", "content": SYNTHESIZER_PROMPT},
                {"role": "user", "content": _findings_text(question, plan, results)}]
    choice = await _complete(llm, model, messages, extra_body, usage, on_event, "synthesizer")
    if choice.finish_reason == "length":
        answer, reason = choice.message.content or None, "output_cut"
    elif choice.finish_reason != "stop":
        answer, reason = choice.message.content or None, choice.finish_reason
    else:
        answer = choice.message.content or None
        reason = "answer" if answer else "empty_answer"

    return MultiAgentResult(
        answer=answer, stop_reason=reason, plan=plan, plan_fallback=fallback,
        findings=[{**s, "stop_reason": r.stop_reason, "steps": r.steps, "seconds": r.seconds,
                   "tool_calls": r.tool_calls, "answer": r.answer} for s, r in zip(plan, results)],
        llm_calls=usage.llm_calls, tool_calls=sum(len(r.tool_calls) for r in results),
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        max_input_tokens=usage.max_input_tokens, research_seconds=research_seconds,
        seconds=round(time.perf_counter() - started, 1))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent (planer, istrazivaci, sintetizator) nad MCP serverom")
    parser.add_argument("question", nargs="?", help="Pitanje na engleskom")
    parser.add_argument("--id", help="ID pitanja iz eval/questions.json, npr. C4")
    args = parser.parse_args()
    if bool(args.question) == bool(args.id):
        parser.error("zadaj ili pitanje ili --id")
    question = args.question or _question_from_eval(args.id)

    load_dotenv(ROOT / ".env")
    llm = AsyncOpenAI(timeout=LLM_TIMEOUT_SECONDS)
    server = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT))
    print(f"Pitanje: {question}\n", flush=True)
    async with Client(server) as mcp:
        result = await run_multi_agent(question, llm, mcp, os.environ["MODEL"], extra_body=provider_options())

    print("\nPlan:" + (" (REZERVNI: planer nije uspeo)" if result.plan_fallback else ""))
    for f in result.findings:
        print(f"  {f['id']}: {f['task']}  -> {f['stop_reason']}, koraka {f['steps']}, alata {len(f['tool_calls'])}")
    print(f"\nKraj: {result.stop_reason} | poziva modela: {result.llm_calls} | poziva alata: {result.tool_calls} "
          f"| tokena ulaz/izlaz: {result.input_tokens}/{result.output_tokens} | {result.seconds} s")
    print(f"\nOdgovor:\n{result.answer}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())

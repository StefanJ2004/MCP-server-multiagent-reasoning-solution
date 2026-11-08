"""Jedan agent: rucna petlja model -> poziv alata -> rezultat -> model, bez frameworka.

Sustina agenta je lista poruka i while petlja:
  1. posaljemo modelu sve dosadasnje poruke i spisak alata
  2. ako model trazi alate: pozovemo ih, rezultate dodamo u listu i vratimo se na 1
  3. ako model vrati tekst bez poziva alata: to je konacan odgovor

Model nikad sam ne izvrsava alate. On samo napise koji alat zeli, a kod ovde ga poziva.

Pokretanje:
  python -m agents.single_agent --id F1
  python -m agents.single_agent "What was Intel's revenue in FY2024?"
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

ROOT = Path(__file__).resolve().parent.parent

MAX_STEPS = 10                # zastita od beskonacne petlje i neocekivanog troska
MAX_OUTPUT_TOKENS = 8192      # gornja granica izlaza po koraku (placa se po tokenu)
LLM_TIMEOUT_SECONDS = 300

SYSTEM_PROMPT = """You are a financial research assistant. Answer using ONLY the tools.

Rules:
- Tool results are correct, even if a date or number looks surprising to you. Never call them hypothetical.
- Use get_financials for numbers and search_filing for explanations.
- fiscal_year is the calendar year in which the fiscal year ENDS. Ignore the company's own naming.
- search_filing is keyword search. Use specific financial terms, not questions. If passages are not relevant, search again with different words.
- Use derived metrics from the tool (margins, rnd_pct, revenue_growth) instead of calculating them.
- If a tool returns an error, fix the arguments and call it again. Use list_companies if you are unsure of a ticker.
- If data is not available, say so. Never estimate or invent numbers.
- If the question has a false premise, correct it using the data.
- Cite the source_id or passage_id in brackets after every number and claim, e.g. [INTC-10K-FY2024].
- When you have enough information, give the final answer briefly, without calling more tools."""


@dataclass
class AgentResult:
    answer: str | None
    stop_reason: str                  # answer | empty_answer | output_cut | max_steps | razlog sa API-ja
    steps: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0             # zbir po koracima: ovo se placa
    output_tokens: int = 0
    max_input_tokens: int = 0         # najduzi pojedinacni prompt: koliko je kontekst narastao
    seconds: float = 0.0


def provider_options() -> dict:
    """Parametri koji nisu deo standardnog OpenAI API-ja i razlikuju se po provajderu.
    Salju se kroz `extra_body`, pa petlja ostaje ista za svaki provajder."""
    thinking = os.environ.get("THINKING", "disabled") == "enabled"
    if "openrouter.ai" in os.environ.get("OPENAI_BASE_URL", ""):
        options = {"reasoning": {"enabled": thinking}}
        if provider := os.environ.get("OPENROUTER_PROVIDER"):
            # only = samo ovaj provajder; allow_fallbacks=False = greska umesto tihog prebacivanja na drugog
            options["provider"] = {"only": [provider], "allow_fallbacks": False}
        return options
    return {"thinking": {"type": "enabled" if thinking else "disabled"}}   # DeepSeek API direktno


def mcp_tools_to_openai(tools) -> list[dict]:
    """MCP i OpenAI opisuju alate istom JSON semom, razlikuje se samo omot oko nje."""
    return [
        {"type": "function",
         "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
        for t in tools
    ]


async def execute_tool(mcp, name: str, raw_arguments: str) -> str:
    """Izvrsava jedan poziv alata. Greske vracamo modelu kao tekst, da moze da ih ispravi."""
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as e:
        return f"Error: arguments are not valid JSON ({e}). Call the tool again with valid JSON."
    result = await mcp.call_tool(name, arguments)
    text = result.content[0].text if result.content else ""
    return f"Error: {text}" if result.is_error else text


def _is_error(output: str) -> bool:
    # Server greske u podacima (npr. nepoznat tiker) vraca kao JSON sa kljucem "error".
    return output.startswith(("Error:", '{"error"'))


def _history_arguments(raw_arguments: str) -> str:
    """Argumenti poziva kakvi se vracaju u istoriji. Neki provajderi (npr. Google Vertex) odbiju CEO
    zahtev (greska 400) ako u istoriji stoji neispravan JSON, pa ga menjamo sa {}. Model i dalje
    dobija poruku o gresci kao rezultat alata i moze da pozove alat ponovo."""
    try:
        json.loads(raw_arguments or "{}")
        return raw_arguments or "{}"
    except json.JSONDecodeError:
        return "{}"


def returned_ids(output: str) -> list[str]:
    """source_id i passage_id iz rezultata alata. Samo njih model sme da citira:
    eval proverava da li citat u odgovoru zaista postoji medju njima."""
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    ids = [data["source_id"]] if "source_id" in data else []          # search_filing
    for row in data.get("results") or []:
        if isinstance(row, dict):
            ids += [row[k] for k in ("source_id", "passage_id") if k in row]   # get_financials / pasusi
    return list(dict.fromkeys(ids))


def _print_event(event: str, **data) -> None:
    print(f"[{event}] " + " ".join(f"{k}={v}" for k, v in data.items()), flush=True)


async def run_agent(question: str, llm, mcp, model: str, extra_body: dict | None = None,
                    max_steps: int = MAX_STEPS, on_event: Callable = _print_event,
                    system_prompt: str = SYSTEM_PROMPT) -> AgentResult:
    """Glavna petlja. `llm` i `mcp` se prosledjuju spolja, pa testovi mogu da podmetnu lazni model,
    a faza 3 pusta vise agenata (istrazivaca) nad istim MCP klijentom, svakog sa svojim system_prompt-om.
    `extra_body` su parametri specificni za provajdera (vidi provider_options)."""
    started = time.perf_counter()
    tools = mcp_tools_to_openai((await mcp.list_tools()).tools)
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    result = AgentResult(answer=None, stop_reason="max_steps")

    def finish(reason: str, answer: str | None = None) -> AgentResult:
        result.stop_reason, result.answer = reason, answer
        result.seconds = round(time.perf_counter() - started, 1)
        return result

    for step in range(1, max_steps + 1):
        result.steps = step
        t0 = time.perf_counter()
        response = await llm.chat.completions.create(
            model=model, messages=messages, tools=tools, max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0,  # sto ponovljiviji eval; bez efekta kad je razmisljanje ukljuceno
            extra_body=extra_body or {})
        choice, usage = response.choices[0], response.usage
        reply = choice.message
        result.input_tokens += usage.prompt_tokens
        result.output_tokens += usage.completion_tokens
        result.max_input_tokens = max(result.max_input_tokens, usage.prompt_tokens)
        # model i provider: ko je STVARNO odgovorio (alias moze da promeni model, OpenRouter provajdera)
        on_event("model", step=step, seconds=round(time.perf_counter() - t0, 1),
                 input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens,
                 finish=choice.finish_reason, model=getattr(response, "model", None),
                 provider=getattr(response, "provider", None))

        # Odsecen ili filtriran izlaz nije odgovor, cak i kad tekst postoji.
        if choice.finish_reason == "length":
            return finish("output_cut", reply.content or None)
        if choice.finish_reason not in ("stop", "tool_calls"):
            return finish(choice.finish_reason, reply.content or None)

        if not reply.tool_calls:
            return finish("answer", reply.content) if reply.content else finish("empty_answer")

        assistant_message = {
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name,
                                         "arguments": _history_arguments(c.function.arguments)}}
                           for c in reply.tool_calls],
        }
        # Uz alate se razmisljanje vraca u sledecem zahtevu, da model nastavi istu misao
        # (DeepSeek direktno inace vraca gresku 400). Polje se razlikuje po provajderu:
        # reasoning_content = DeepSeek API, reasoning_details = OpenRouter.
        for field_name in ("reasoning_content", "reasoning_details"):
            value = getattr(reply, field_name, None)
            if value:
                assistant_message[field_name] = value
        messages.append(assistant_message)

        for call in reply.tool_calls:
            name, arguments = call.function.name, call.function.arguments
            output = await execute_tool(mcp, name, arguments)
            ids, error = returned_ids(output), _is_error(output)
            result.tool_calls.append({"name": name, "arguments": arguments, "error": error, "returned_ids": ids})
            on_event("tool", name=name, arguments=arguments, result_chars=len(output), error=error,
                     returned_ids=ids)
            # tool_call_id povezuje rezultat sa pozivom; bez njega model ne zna cemu rezultat pripada
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

    return finish("max_steps")


def _question_from_eval(question_id: str) -> str:
    data = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    for q in data["questions"]:
        if q["id"] == question_id:
            return q["question_en"]
    sys.exit(f"Nema pitanja {question_id} u eval/questions.json")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Jedan agent nad MCP serverom")
    parser.add_argument("question", nargs="?", help="Pitanje na engleskom")
    parser.add_argument("--id", help="ID pitanja iz eval/questions.json, npr. F1")
    args = parser.parse_args()
    if bool(args.question) == bool(args.id):
        parser.error("zadaj ili pitanje ili --id")
    question = args.question or _question_from_eval(args.id)

    load_dotenv(ROOT / ".env")
    llm = AsyncOpenAI(timeout=LLM_TIMEOUT_SECONDS)   # OPENAI_BASE_URL i OPENAI_API_KEY cita iz okruzenja
    server = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT))
    print(f"Pitanje: {question}\n", flush=True)
    async with Client(server) as mcp:
        result = await run_agent(question, llm, mcp, os.environ["MODEL"], extra_body=provider_options())

    print(f"\nKraj: {result.stop_reason} | koraka: {result.steps} | poziva alata: {len(result.tool_calls)} "
          f"| tokena ulaz/izlaz: {result.input_tokens}/{result.output_tokens} | {result.seconds} s")
    print(f"\nOdgovor:\n{result.answer}")


if __name__ == "__main__":
    # Windows konzola ne ume sve Unicode znakove iz 10-K teksta.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())

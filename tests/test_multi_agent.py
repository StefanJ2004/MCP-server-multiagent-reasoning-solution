"""Testovi multi-agenta sa laznim modelom: mehanika orkestracije, ne kvalitet modela.

Istrazivaci rade paralelno, pa redosled poziva nije unapred poznat. Zato lazni model odgovara
po ULOZI pozivaoca: planer salje response_format, istrazivac salje tools, sintetizator nista od toga.
Alati i podaci su pravi (MCP server u istom procesu, JEDNA veza za sve istrazivace).
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from agents.multi_agent import MAX_SUBTASKS, RESEARCHER_PROMPT, parse_plan, run_multi_agent
from mcp import Client
from mcp_server.search import FILINGS_DIR
from mcp_server.server import server

needs_data = pytest.mark.skipif(
    not (FILINGS_DIR / "manifest.json").exists(), reason="nema podataka - pokreni scripts/download_data.py"
)

# tiker -> (godina, prihod iz pravih podataka)
REVENUE = {"INTC": (2024, 53.101), "NVDA": (2024, 60.922), "MU": (2023, 15.54)}


def response(content="", tool_calls=None, finish=None):
    finish = finish or ("tool_calls" if tool_calls else "stop")
    message = NS(content=content, tool_calls=tool_calls, reasoning_content=None, reasoning_details=None)
    return NS(choices=[NS(message=message, finish_reason=finish)],
              usage=NS(prompt_tokens=100, completion_tokens=10))


def plan_json(*tickers):
    return json.dumps({"subtasks": [{"id": f"x{i}", "task": f"{t} revenue"} for i, t in enumerate(tickers)]})


class RoleLLM:
    """Lazni model koji odgovara po ulozi i meri koliko istrazivaca radi ISTOVREMENO."""

    def __init__(self, *planner_replies):
        self.planner_replies = list(planner_replies)
        self.planner_requests, self.researcher_requests, self.synth_requests = [], [], []
        self.in_flight = self.max_in_flight = 0
        self.chat = NS(completions=NS(create=self._create))

    async def _create(self, **kw):
        if "response_format" in kw:
            self.planner_requests.append(list(kw["messages"]))
            return response(self.planner_replies.pop(0))
        if "tools" in kw:
            return await self._researcher(kw["messages"])
        self.synth_requests.append(list(kw["messages"]))
        return response("Final.")

    async def _researcher(self, messages):
        self.researcher_requests.append(list(messages))
        ticker = messages[1]["content"].split("Subtask: ")[1].split()[0]
        if ticker == "FAIL":
            raise RuntimeError("provajder ne radi")
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.05)              # "model razmislja" - dok ovaj ceka, drugi mogu da krenu
        self.in_flight -= 1
        if messages[-1]["role"] == "tool":     # drugi korak: procitaj rezultat alata i odgovori
            revenue = json.loads(messages[-1]["content"])["results"][0]["revenue"]
            return response(f"{ticker} revenue {revenue}")
        year = REVENUE[ticker][0]
        args = json.dumps({"ticker": ticker, "metrics": ["revenue"], "fiscal_years": [year]})
        return response(tool_calls=[NS(id="call_1", function=NS(name="get_financials", arguments=args))])


def run(llm, question="Compare revenue.", **kwargs):
    async def go():
        async with Client(server) as mcp:
            return await run_multi_agent(question, llm, mcp, "fake", on_event=lambda *a, **k: None, **kwargs)
    return asyncio.run(go())


# --- parse_plan (bez modela) ------------------------------------------------------

def test_parse_plan_assigns_own_ids():
    plan = parse_plan('{"subtasks": [{"id": "a", "task": "INTC revenue"}, {"id": "a", "task": "AMD revenue"}]}')
    assert [p["id"] for p in plan] == ["t1", "t2"]          # duplikat "a" ne smeta


def test_parse_plan_caps_number_of_subtasks():
    many = json.dumps({"subtasks": [{"task": f"task {i}"} for i in range(30)]})
    assert len(parse_plan(many)) == MAX_SUBTASKS


@pytest.mark.parametrize("text, error", [
    ("not json", "not valid JSON"),
    ('{"subtasks": []}', "non-empty list"),
    ('{"tasks": [{"task": "x"}]}', "non-empty list"),
    ('{"subtasks": [{"id": "t1"}]}', 'no "task"'),
])
def test_parse_plan_errors_explain_what_is_wrong(text, error):
    with pytest.raises(ValueError, match=error):
        parse_plan(text)


# --- ceo tok ----------------------------------------------------------------------

@needs_data
def test_full_flow_planner_researchers_synthesizer():
    llm = RoleLLM(plan_json("INTC", "NVDA"))
    result = run(llm)
    assert result.stop_reason == "answer" and result.answer == "Final."
    assert [f["stop_reason"] for f in result.findings] == ["answer", "answer"]
    # pravi podaci prosli kroz deljenu MCP vezu do pravog istrazivaca
    assert result.findings[0]["answer"] == "INTC revenue 53.101"
    assert result.findings[1]["answer"] == "NVDA revenue 60.922"
    # sintetizator dobija pitanje i sve nalaze
    synth_input = llm.synth_requests[0][1]["content"]
    assert "Compare revenue." in synth_input
    assert "### t1: INTC revenue\nINTC revenue 53.101" in synth_input and "### t2" in synth_input
    # 1 planer + 2 istrazivaca x 2 koraka + 1 sintetizator
    assert (result.llm_calls, result.tool_calls) == (6, 2)
    assert result.input_tokens == 600


@needs_data
def test_planner_gets_company_list():
    llm = RoleLLM(plan_json("INTC"))
    run(llm)
    system = llm.planner_requests[0][0]["content"]
    assert "- NVDA: NVIDIA CORP, semiconductors" in system and "HD:" in system


@needs_data
def test_researcher_gets_own_prompt_and_subtask_only():
    llm = RoleLLM(plan_json("INTC"))
    run(llm, question="Compare revenue.")
    system, user = llm.researcher_requests[0][:2]
    assert system["content"] == RESEARCHER_PROMPT
    assert user["content"].startswith("Subtask: INTC revenue")
    assert "Original question (context only): Compare revenue." in user["content"]


@needs_data
def test_researchers_run_in_parallel():
    llm = RoleLLM(plan_json("INTC", "NVDA", "MU"))
    result = run(llm)
    assert llm.max_in_flight == 3                     # sva tri su "razmisljala" u isto vreme
    assert result.findings[2]["answer"] == "MU revenue 15.54"


@needs_data
def test_parallelism_is_limited():
    llm = RoleLLM(plan_json("INTC", "NVDA", "MU", "INTC", "NVDA"))
    run(llm, max_parallel=2)
    assert llm.max_in_flight == 2


@needs_data
def test_invalid_plan_gets_second_chance():
    llm = RoleLLM("ovo nije json", plan_json("INTC"))
    result = run(llm)
    assert not result.plan_fallback and len(result.plan) == 1
    retry_message = llm.planner_requests[1][-1]["content"]
    assert retry_message.startswith("Your plan is invalid: not valid JSON")


@needs_data
def test_two_invalid_plans_fall_back_to_single_researcher():
    llm = RoleLLM("los", "opet los")
    result = run(llm, question="INTC revenue in FY2024?")
    assert result.plan_fallback
    assert result.plan == [{"id": "t1", "task": "INTC revenue in FY2024?"}]
    assert result.findings[0]["stop_reason"] == "answer"


@needs_data
def test_failed_researcher_does_not_stop_others():
    llm = RoleLLM(plan_json("INTC", "FAIL"))
    result = run(llm)
    assert result.findings[0]["stop_reason"] == "answer"
    assert result.findings[1]["stop_reason"].startswith("error:")
    assert "NO RESULT (researcher stopped: error: provajder ne radi)" in llm.synth_requests[0][1]["content"]
    assert result.stop_reason == "answer"

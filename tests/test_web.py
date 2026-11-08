"""Testovi web backend-a bez HTTP-a: generator dogadjaja (lazni model, pravi alati) i citati."""
import asyncio
import json

import pytest

from mcp import Client
from mcp_server.search import FILINGS_DIR
from mcp_server.server import server
from test_multi_agent import RoleLLM, plan_json
from test_single_agent import FakeLLM, reply
from web.server import passage, run_events

pytestmark = pytest.mark.skipif(
    not (FILINGS_DIR / "manifest.json").exists(), reason="nema podataka - pokreni scripts/download_data.py"
)


def collect(llm, mode, question="Q"):
    async def go():
        async with Client(server) as mcp:
            return [e async for e in run_events(question, mode, llm, mcp, "fake", {})]
    events = asyncio.run(go())
    for e in events:
        json.dumps(e, default=str)          # sve mora da prodje kroz SSE kao JSON
    return events


def test_single_agent_events_in_order():
    events = collect(FakeLLM(reply(tool="get_financials"), reply("Kraj.")), "single")
    assert [e["type"] for e in events] == ["run_start", "model", "tool", "model", "done"]
    tool = events[2]
    assert tool["name"] == "get_financials" and tool["returned_ids"] == ["INTC-10K-FY2024"]
    done = events[-1]
    assert (done["answer"], done["stop_reason"], done["llm_calls"], done["tool_calls"]) == ("Kraj.", "answer", 2, 1)
    assert done["cost"] is None                     # "fake" model nema cenu
    assert all(b["t"] >= a["t"] for a, b in zip(events, events[1:]))   # vreme ide napred


def test_multi_agent_events_show_plan_and_researchers():
    events = collect(RoleLLM(plan_json("INTC", "NVDA")), "multi")
    plan = next(e for e in events if e["type"] == "plan")
    assert [t["task"] for t in plan["tasks"]] == ["INTC revenue", "NVDA revenue"]
    starts = {e["agent"] for e in events if e["type"] == "start"}
    assert starts == {"researcher:t1", "researcher:t2"}
    findings = {e["agent"]: e["answer"] for e in events if e["type"] == "finish"}
    assert findings == {"researcher:t1": "INTC revenue 53.101", "researcher:t2": "NVDA revenue 60.922"}
    assert any(e["type"] == "model" and e["agent"] == "synthesizer" for e in events)
    done = events[-1]
    assert done["type"] == "done" and done["answer"] == "Final." and len(done["plan"]) == 2


def test_api_error_becomes_error_event():
    class BrokenLLM:
        def __init__(self):
            async def create(**kwargs):
                raise RuntimeError("provajder ne radi")
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(create)})})
    events = collect(BrokenLLM(), "single")
    assert [e["type"] for e in events] == ["run_start", "error"]
    assert "provajder ne radi" in events[-1]["error"]


def test_passage_text_for_citation():
    p = passage("MU-10K-FY2023#p221")
    assert p["section"] and "deteriorated sharply" in p["text"]
    assert p["url"].startswith("https://www.sec.gov/")


def test_passage_for_whole_report_and_errors():
    whole = passage("INTC-10K-FY2024")
    assert whole["period_end"] == "2024-12-28" and "text" not in whole
    assert "error" in passage("[t1]")
    assert "error" in passage("INTC-10K-FY2019")
    assert "error" in passage("MU-10K-FY2023#p999999")

"""Testovi agent petlje sa laznim modelom: brzi su i proveravaju mehaniku, ne kvalitet modela.

Lazni model vraca unapred zadate odgovore, a alati su pravi (MCP server u istom procesu).
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from agents.single_agent import mcp_tools_to_openai, run_agent
from mcp import Client
from mcp_server.search import FILINGS_DIR
from mcp_server.server import server

pytestmark = pytest.mark.skipif(
    not (FILINGS_DIR / "manifest.json").exists(), reason="nema podataka - pokreni scripts/download_data.py"
)

INTC_ARGS = json.dumps({"ticker": "INTC", "metrics": ["revenue"], "fiscal_years": [2024]})


def reply(content="", tool=None, arguments=INTC_ARGS, finish=None, prompt_tokens=100, reasoning=None):
    calls = None
    if tool:
        calls = [NS(id="call_1", function=NS(name=tool, arguments=arguments))]
    message = NS(content=content, tool_calls=calls, reasoning_content=reasoning)
    finish = finish or ("tool_calls" if tool else "stop")
    return NS(choices=[NS(message=message, finish_reason=finish)],
              usage=NS(prompt_tokens=prompt_tokens, completion_tokens=10))


class FakeLLM:
    """Pamti sta je dobio i vraca sledeci zadati odgovor (poslednji se ponavlja)."""
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []
        self.chat = NS(completions=NS(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


def run(llm, question="Q", **kwargs):
    async def go():
        async with Client(server) as mcp:
            return await run_agent(question, llm, mcp, "fake", on_event=lambda *a, **k: None, **kwargs)
    return asyncio.run(go())


def test_tools_are_translated_to_openai_format():
    async def go():
        async with Client(server) as mcp:
            return mcp_tools_to_openai((await mcp.list_tools()).tools)
    tools = {t["function"]["name"]: t for t in asyncio.run(go())}
    assert set(tools) == {"list_companies", "get_financials", "search_filing"}
    assert tools["get_financials"]["type"] == "function"
    assert "metrics" in tools["get_financials"]["function"]["parameters"]["properties"]


def test_answer_without_tools_ends_loop():
    llm = FakeLLM(reply("Gotovo."))
    result = run(llm)
    assert (result.stop_reason, result.answer, result.steps) == ("answer", "Gotovo.", 1)
    assert llm.requests[0]["messages"][-1]["content"] == "Q"


def test_tool_result_goes_back_to_model():
    llm = FakeLLM(reply(tool="get_financials"), reply("Prihod je 53.101."))
    result = run(llm)
    assert result.stop_reason == "answer" and result.steps == 2
    assistant, tool = llm.requests[1]["messages"][-2:]
    assert assistant["tool_calls"][0]["function"]["name"] == "get_financials"
    assert tool["role"] == "tool" and tool["tool_call_id"] == "call_1"
    assert json.loads(tool["content"])["results"][0]["revenue"] == 53.101


def test_reasoning_is_passed_back_when_present():
    # DeepSeek vraca gresku 400 ako se razmisljanje ne vrati u sledecem zahtevu uz alate.
    llm = FakeLLM(reply(tool="get_financials", reasoning="razmisljanje"), reply("Kraj."))
    run(llm)
    assert llm.requests[1]["messages"][-2]["reasoning_content"] == "razmisljanje"


def test_no_reasoning_field_when_thinking_is_off():
    llm = FakeLLM(reply(tool="get_financials"), reply("Kraj."))
    run(llm)
    assert "reasoning_content" not in llm.requests[1]["messages"][-2]


def test_thinking_setting_is_sent_to_api():
    llm = FakeLLM(reply("Kraj."))
    run(llm, thinking="enabled")
    assert llm.requests[0]["extra_body"] == {"thinking": {"type": "enabled"}}


def test_tokens_are_summed_across_steps():
    result = run(FakeLLM(reply(tool="get_financials", prompt_tokens=100), reply("Kraj.", prompt_tokens=300)))
    assert (result.input_tokens, result.output_tokens) == (400, 20)


def test_invalid_json_arguments_go_back_as_error():
    llm = FakeLLM(reply(tool="get_financials", arguments="{nije json"), reply("Kraj."))
    result = run(llm)
    assert result.stop_reason == "answer"
    assert llm.requests[1]["messages"][-1]["content"].startswith("Error: arguments are not valid JSON")


def test_tool_error_goes_back_as_error():
    bad = json.dumps({"ticker": "INTC", "metrics": ["ebitda"], "fiscal_years": [2024]})
    llm = FakeLLM(reply(tool="get_financials", arguments=bad), reply("Kraj."))
    run(llm)
    content = llm.requests[1]["messages"][-1]["content"]
    assert content.startswith("Error:") and "net_margin" in content


def test_cut_output_is_not_an_answer():
    result = run(FakeLLM(reply("pocetak odgovora", finish="length")))
    assert result.stop_reason == "output_cut"


def test_empty_reply_is_not_an_answer():
    result = run(FakeLLM(reply("")))
    assert (result.stop_reason, result.answer) == ("empty_answer", None)


def test_filtered_output_is_not_an_answer():
    result = run(FakeLLM(reply("delimicno", finish="content_filter")))
    assert result.stop_reason == "content_filter"


def test_step_limit_stops_loop():
    llm = FakeLLM(reply(tool="get_financials"))
    result = run(llm, max_steps=3)
    assert result.stop_reason == "max_steps" and len(llm.requests) == 3

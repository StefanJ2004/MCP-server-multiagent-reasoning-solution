"""Testovi MCP sloja: ono sto model vidi (imena, opisi, seme) i kako izgledaju odgovori.

Vecina testova povezuje klijenta direktno na server objekat (u istom procesu, brzo).
Poslednji test pokrece server kao pravi podproces preko stdio-a - isto kao agent i Claude Desktop.
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from mcp import Client, StdioServerParameters
from mcp_server.search import FILINGS_DIR
from mcp_server.server import server

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    not (FILINGS_DIR / "manifest.json").exists(), reason="nema podataka - pokreni scripts/download_data.py"
)


def run(coro):
    return asyncio.run(coro)


async def _tools(target):
    async with Client(target) as c:
        return {t.name: t for t in (await c.list_tools()).tools}


async def _call(name, args, target=server):
    async with Client(target) as c:
        return await c.call_tool(name, args)


def test_exactly_three_tools_with_descriptions():
    tools = run(_tools(server))
    assert set(tools) == {"list_companies", "get_financials", "search_filing"}
    for t in tools.values():
        assert t.description and len(t.description) > 100   # opis je jedino sto model zna o alatu
        assert t.annotations.read_only_hint is True


def test_metric_enum_in_schema():
    schema = run(_tools(server))["get_financials"].input_schema
    enum = schema["properties"]["metrics"]["items"]["enum"]
    assert "net_margin" in enum and "ebitda" not in enum


def test_get_financials_returns_compact_json():
    result = run(_call("get_financials", {"ticker": "INTC", "metrics": ["net_income"], "fiscal_years": [2024]}))
    assert not result.is_error
    text = result.content[0].text
    assert "\n" not in text                                   # kompaktno, jedna linija
    assert json.loads(text)["results"][0]["net_income"] == -18.756


def test_invalid_metric_is_tool_error_listing_valid_values():
    result = run(_call("get_financials", {"ticker": "INTC", "metrics": ["ebitda"], "fiscal_years": [2024]}))
    assert result.is_error
    assert "net_margin" in result.content[0].text


def test_search_filing_through_mcp():
    result = run(_call("search_filing", {"ticker": "MU", "fiscal_year": 2023, "query": "weak demand pricing"}))
    data = json.loads(result.content[0].text)
    assert data["source_id"] == "MU-10K-FY2023"
    assert len(data["results"]) == 3


def test_server_runs_over_stdio_subprocess():
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT))
    result = run(_call("list_companies", {"sector": "retail"}, target=params))
    tickers = {c["ticker"] for c in json.loads(result.content[0].text)["companies"]}
    assert tickers == {"HD", "LOW", "BBY", "DG"}

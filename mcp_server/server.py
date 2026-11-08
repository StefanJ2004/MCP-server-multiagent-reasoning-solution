"""MCP server: izlaze finansijske podatke i tekst 10-K izvestaja kao 3 alata.

Ovaj fajl je namerno tanak - sva logika je u financials.py i search.py.
Ovde je bitno samo ono sto model vidi:
  - IME alata
  - OPIS alata (docstring) - jedino sto model zna o tome kada i kako da koristi alat
  - SEMA parametara (iz tipova) - Literal postaje enum, pa model ne moze da izmisli metriku

Pokretanje (stdio, kako ga pokrecu agenti i Claude Desktop):  python -m mcp_server.server
"""
import json
from typing import Annotated, Literal

from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from mcp_server import financials, search

Sector = Literal["semiconductors", "software", "retail"]
Metric = Literal[
    "revenue", "gross_profit", "operating_income", "net_income", "rnd",
    "gross_margin", "operating_margin", "net_margin", "rnd_pct", "revenue_growth",
]
assert set(Metric.__args__) == set(financials.ALL_METRICS), "Metric enum mora da prati financials.py"

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def _to_json(obj: dict) -> str:
    """Kompaktan JSON u jednoj liniji: ~20% manje tokena od uvucenog, a model ga cita isto dobro.
    Na CPU-u svaki token ulaza kosta vreme."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


server = MCPServer(
    name="sec-edgar-research",
    instructions=(
        "Financial data and 10-K annual report text for 18 US public companies "
        "(semiconductors, software, retail), fiscal years 2022 onward. "
        "Use get_financials for numbers and search_filing for explanations. "
        "fiscal_year always means the calendar year in which the fiscal year ENDS. "
        "Cite source_id / passage_id for every number and claim."
    ),
)


@server.tool(annotations=READ_ONLY)
def list_companies(
    sector: Annotated[Sector | None, Field(description="Optional sector filter.")] = None,
) -> str:
    """List the companies covered by this server, with ticker, sector, fiscal year end date
    and the fiscal years for which data is available.
    Call this first if you are unsure which tickers or fiscal years exist."""
    return _to_json({"companies": financials.list_companies(sector)})


@server.tool(annotations=READ_ONLY)
def get_financials(
    ticker: Annotated[str, Field(description="Stock ticker, e.g. 'NVDA'.")],
    metrics: Annotated[list[Metric], Field(description="One or more metrics to return.")],
    fiscal_years: Annotated[list[int], Field(description="One or more fiscal years, e.g. [2023, 2024].")],
) -> str:
    """Get annual financial figures for ONE company from its 10-K filings (SEC EDGAR).

    Base metrics, in USD billions: revenue, gross_profit, operating_income, net_income,
    rnd (research and development expense).
    Derived metrics, in percent, already computed by the server (do not recalculate them):
    gross_margin, operating_margin, net_margin, rnd_pct (R&D as % of revenue),
    revenue_growth (change vs the previous fiscal year).

    fiscal_year = calendar year in which the company's fiscal year ENDS. Example: Home Depot's
    year ending 2025-02-02 is fiscal_year 2025, even though Home Depot calls it "fiscal 2024".
    Each result includes the exact period dates and a source_id to cite.
    If a year is not available the response says so - never estimate or invent missing values.
    To compare several companies, call this tool once per company."""
    return _to_json(financials.get_financials(ticker, list(metrics), fiscal_years))


@server.tool(annotations=READ_ONLY)
def search_filing(
    ticker: Annotated[str, Field(description="Stock ticker, e.g. 'MU'.")],
    fiscal_year: Annotated[int, Field(description="Fiscal year of the 10-K report (year the fiscal year ends).")],
    query: Annotated[str, Field(description="Specific financial terms, e.g. 'inventory write-down'.")],
) -> str:
    """Search the text of ONE company's 10-K annual report for one fiscal year.
    Returns the 3 most relevant passages with their section name and passage_id.

    Use it to find explanations: why revenue or profit changed, charges and impairments,
    segment drivers, industry conditions.
    This is keyword search (BM25). Use specific terms that would appear in the report,
    e.g. 'inventory write-down', 'valuation allowance deferred tax', 'data center revenue' -
    NOT questions like 'why did profit fall'. If the passages are not relevant, search again
    with different terms. Cite passages by passage_id."""
    return _to_json(search.search_filing(ticker, fiscal_year, query))


if __name__ == "__main__":
    server.run()  # stdio transport

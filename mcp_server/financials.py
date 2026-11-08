"""Finansijski brojevi iz SEC EDGAR companyfacts JSON-a.

Ovde se resavaju sve zamke iz faze 0, da ih model nikad ne bi video:
  1. duplikati - isti period se ponavlja u vise 10-K prijava
  2. polje `fy` je nepouzdano - fiskalnu godinu racunamo sami iz datuma kraja perioda
  3. kompanije razlicito imenuju fiskalnu godinu - nasa konvencija: FY = godina zavrsetka
  4. ista metrika pod vise XBRL tagova - mapa tagova, a redosled tagova je prioritet

Modul je cist Python (bez MCP-a), pa se testira direktno: tests/test_financials.py
"""
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from mcp_server.companies import COMPANIES

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "companyfacts"

# Redosled je bitan: uzima se prvi tag koji ima vrednost za datu godinu.
# Npr. NetIncomeLoss (pripada akcionarima) ima prednost nad ProfitLoss (ukljucuje manjinske udele).
TAG_PRIORITY: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "rnd": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
        "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost",
    ],
}
BASE_METRICS = list(TAG_PRIORITY)

# Izvedene metrike racuna server (mali model lose racuna). Sve su u procentima.
DERIVED_METRICS = {
    "gross_margin": ("gross_profit", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "net_margin": ("net_income", "revenue"),
    "rnd_pct": ("rnd", "revenue"),
    "revenue_growth": None,  # poseban slucaj: poredi sa prethodnom godinom
}
ALL_METRICS = BASE_METRICS + list(DERIVED_METRICS)

# Fiskalna godina traje 52 ili 53 nedelje (364 ili 371 dan), a kvartali ~91 dan.
MIN_ANNUAL_DAYS, MAX_ANNUAL_DAYS = 350, 380


@dataclass(frozen=True)
class Fact:
    """Jedna godisnja vrednost jedne metrike, sa poreklom."""
    value: float          # u dolarima
    period_start: str
    period_end: str
    tag: str              # XBRL tag iz kog je vrednost uzeta
    accession: str        # broj SEC prijave iz koje je vrednost
    filed: str

    @property
    def fiscal_year(self) -> int:
        return int(self.period_end[:4])


@lru_cache(maxsize=None)
def _load(ticker: str) -> dict:
    """Ucitava companyfacts JSON jednom po kompaniji (fajlovi su 3-5 MB)."""
    return json.loads((DATA_DIR / f"{ticker}.json").read_text(encoding="utf-8"))


def _is_annual(record: dict) -> bool:
    if record.get("form") != "10-K" or "start" not in record:
        return False
    days = (date.fromisoformat(record["end"]) - date.fromisoformat(record["start"])).days
    return MIN_ANNUAL_DAYS <= days <= MAX_ANNUAL_DAYS


@lru_cache(maxsize=None)
def annual_facts(ticker: str, metric: str) -> dict[int, Fact]:
    """Sve godisnje vrednosti jedne metrike: {fiskalna_godina: Fact}.

    Za svaku godinu uzima se prvi tag po prioritetu koji ima vrednost (zamka 4).
    Unutar taga, isti period se javlja u vise prijava (zamka 1); uzimamo ORIGINALNU
    prijavu (najraniji `filed`) - to je 10-K bas te godine, pa citat vodi na pravi izvestaj.
    """
    gaap = _load(ticker)["facts"]["us-gaap"]
    result: dict[int, Fact] = {}
    for tag in TAG_PRIORITY[metric]:
        records = gaap.get(tag, {}).get("units", {}).get("USD", [])
        best_for_year: dict[int, Fact] = {}
        for r in filter(_is_annual, records):
            fact = Fact(r["val"], r["start"], r["end"], tag, r["accn"], r["filed"])
            current = best_for_year.get(fact.fiscal_year)
            if current is None or fact.filed < current.filed:
                best_for_year[fact.fiscal_year] = fact
        for year, fact in best_for_year.items():
            result.setdefault(year, fact)  # visi prioritet je vec upisan - ne gazimo ga
    return result


def company_name(ticker: str) -> str:
    return _load(ticker)["entityName"]


def list_companies(sector: str | None = None) -> list[dict]:
    """Kompanije koje sistem pokriva, sa godinama za koje postoje podaci."""
    out = []
    for ticker, sec in COMPANIES.items():
        if sector and sec != sector:
            continue
        revenue = annual_facts(ticker, "revenue")
        latest = revenue[max(revenue)]
        out.append({
            "ticker": ticker,
            "name": company_name(ticker),
            "sector": sec,
            "fiscal_year_ends": latest.period_end[5:],  # MM-DD poslednje fiskalne godine
            "fiscal_years_available": sorted(y for y in revenue if y >= 2018),
        })
    return out


def _source_id(ticker: str, fact: Fact) -> str:
    """Isti format koristi i search_filing, pa agent moze da poveze broj i tekst."""
    return f"{ticker}-10K-FY{fact.fiscal_year}"


def _derived(ticker: str, metric: str, year: int) -> float | None:
    if metric == "revenue_growth":
        revenue = annual_facts(ticker, "revenue")
        if year not in revenue or year - 1 not in revenue:
            return None
        return (revenue[year].value / revenue[year - 1].value - 1) * 100
    numerator, denominator = DERIVED_METRICS[metric]
    num = annual_facts(ticker, numerator).get(year)
    den = annual_facts(ticker, denominator).get(year)
    if num is None or den is None or den.value == 0:
        return None
    return num.value / den.value * 100


def get_financials(ticker: str, metrics: list[str], fiscal_years: list[int]) -> dict:
    """Glavni alat. Vraca recnik spreman za JSON odgovor modelu.

    Greske (nepoznat tiker, metrika, godina bez podataka) se NE bacaju kao izuzeci,
    vec se vracaju kao poruke - model iz njih uci sta da promeni u sledecem pozivu.
    """
    ticker = ticker.upper().strip()
    if ticker not in COMPANIES:
        return {"error": f"Unknown ticker '{ticker}'. Available: {', '.join(COMPANIES)}"}
    unknown = [m for m in metrics if m not in ALL_METRICS]
    if unknown:
        return {"error": f"Unknown metric(s) {unknown}. Available: {', '.join(ALL_METRICS)}"}

    revenue = annual_facts(ticker, "revenue")
    results, missing = [], []
    for year in sorted(set(fiscal_years)):
        if year not in revenue:
            missing.append(year)
            continue
        anchor = revenue[year]  # period i izvor uzimamo od prihoda za tu godinu
        row: dict = {
            "fiscal_year": year,
            "period": f"{anchor.period_start}..{anchor.period_end}",
            "source_id": _source_id(ticker, anchor),
        }
        for m in metrics:
            if m in DERIVED_METRICS:
                value = _derived(ticker, m, year)
                row[m] = None if value is None else round(value, 1)
            else:
                fact = annual_facts(ticker, m).get(year)
                row[m] = None if fact is None else round(fact.value / 1e9, 3)
        results.append(row)

    response: dict = {
        "ticker": ticker,
        "company": company_name(ticker),
        "units": "base metrics in USD billions; margins, rnd_pct and revenue_growth in percent",
        "fiscal_year_convention": "fiscal_year = calendar year in which the fiscal year ENDS",
        "results": results,
    }
    if missing:
        available = sorted(y for y in revenue if y >= 2018)
        response["not_available"] = (
            f"No data for fiscal year(s) {missing}. Available: {available}. "
            "Do not estimate or invent values for missing years."
        )
    return response

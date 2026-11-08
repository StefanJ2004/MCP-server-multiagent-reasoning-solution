"""Testovi za mcp_server/financials.py.

Tacne vrednosti su iz eval/questions.json (proverene u fazi 0), plus po jedan test
za svaku zamku u podacima. Potrebni su skinuti podaci: python scripts/download_data.py
"""
import pytest

from mcp_server import financials as fin

pytestmark = pytest.mark.skipif(
    not (fin.DATA_DIR / "NVDA.json").exists(), reason="nema podataka - pokreni scripts/download_data.py"
)


def value(ticker, metric, year):
    row = fin.get_financials(ticker, [metric], [year])["results"][0]
    return row[metric]


# --- tacni odgovori iz eval seta ------------------------------------------------

@pytest.mark.parametrize("ticker, metric, year, expected", [
    ("INTC", "revenue", 2024, 53.101),           # F1
    ("AMAT", "gross_margin", 2024, 47.5),       # F2
    ("BBY", "net_income", 2025, 0.927),         # F3
    ("NVDA", "revenue", 2023, 26.974),          # C1
    ("NVDA", "revenue", 2025, 130.497),
    ("AMD", "revenue", 2025, 34.639),
    ("INTC", "revenue", 2023, 54.228),
    ("ADBE", "operating_margin", 2025, 36.6),   # C2
    ("CRM", "operating_margin", 2025, 19.0),
    ("NOW", "operating_margin", 2025, 13.7),
    ("ADI", "rnd_pct", 2024, 15.8),             # C3
    ("MU", "rnd_pct", 2024, 13.7),
    ("TXN", "rnd_pct", 2024, 12.5),
    ("HD", "net_margin", 2023, 10.9),           # C4
    ("HD", "net_margin", 2025, 9.3),
    ("LOW", "net_margin", 2024, 8.9),
    ("LOW", "revenue", 2025, 83.674),
    ("INTC", "net_income", 2024, -18.756),      # E1
    ("NVDA", "revenue_growth", 2024, 125.9),    # E2
    ("MU", "net_income", 2023, -5.833),         # E3
    ("HD", "net_income", 2025, 14.806),         # U2 (nije bilo gubitka)
])
def test_eval_values(ticker, metric, year, expected):
    assert value(ticker, metric, year) == expected


# --- zamke iz faze 0 -----------------------------------------------------------

def test_duplicates_resolved_to_original_filing():
    """Zamka 1: NVDA prihod FY2023 je u 3 prijave; uzimamo originalnu (10-K za FY2023)."""
    fact = fin.annual_facts("NVDA", "revenue")[2023]
    assert fact.filed == "2023-02-24"


def test_fiscal_year_is_year_of_period_end():
    """Zamke 2 i 3: HD period koji se zavrsava 2025-02-02 je nasa FY2025 (HD ga zove fiscal 2024)."""
    row = fin.get_financials("HD", ["revenue"], [2025])["results"][0]
    assert row["period"] == "2024-01-29..2025-02-02"
    assert row["revenue"] == 159.514


def test_tag_switch_over_time():
    """Zamka 4: NVDA prihod je do FY2022 pod drugim tagom, posle pod 'Revenues'."""
    facts = fin.annual_facts("NVDA", "revenue")
    assert facts[2024].tag == "Revenues"
    assert facts[2022].value == 26_914_000_000


def test_tag_priority_not_min():
    """Greska iz faze 0: INTC ima i NetIncomeLoss i ProfitLoss; mora NetIncomeLoss."""
    fact = fin.annual_facts("INTC", "net_income")[2024]
    assert fact.tag == "NetIncomeLoss"


# --- ponasanje alata -----------------------------------------------------------

def test_missing_year_is_reported_not_invented():
    """U1: FY2030 ne postoji - alat to jasno kaze."""
    resp = fin.get_financials("INTC", ["net_income"], [2030])
    assert resp["results"] == []
    assert "2030" in resp["not_available"]


def test_unknown_ticker_and_metric_return_errors():
    assert "Unknown ticker" in fin.get_financials("AAPL", ["revenue"], [2024])["error"]
    assert "Unknown metric" in fin.get_financials("NVDA", ["ebitda"], [2024])["error"]


def test_ticker_is_case_insensitive():
    assert value("nvda", "revenue", 2024) == 60.922


def test_source_id_and_period_present():
    row = fin.get_financials("MU", ["revenue", "net_income"], [2023])["results"][0]
    assert row["source_id"] == "MU-10K-FY2023"
    assert row["period"] == "2022-09-02..2023-08-31"


def test_list_companies_by_sector():
    retail = fin.list_companies("retail")
    assert {c["ticker"] for c in retail} == {"HD", "LOW", "BBY", "DG"}
    assert all(2024 in c["fiscal_years_available"] for c in retail)
    assert len(fin.list_companies()) == 18

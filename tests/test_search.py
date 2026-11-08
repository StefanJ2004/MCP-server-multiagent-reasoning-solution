"""Testovi za mcp_server/search.py.

Jedinicni testovi rade bez podataka. Integracioni testovi (E1-E3) proveravaju da pretraga
nad pravim 10-K izvestajima vraca pasuse koje smo rucno nasli u fazi 0.
"""
import pytest

from mcp_server import search as s
from mcp_server.financials import get_financials

# --- normalizacija i tokenizacija ------------------------------------------------

@pytest.mark.parametrize("word, expected", [
    ("inventories", "inventory"),
    ("downs", "down"),
    ("taxes", "tax"),
    ("prices", "price"),
    ("loss", "loss"),        # -ss ostaje
    ("gross", "gross"),
    ("revenue", "revenue"),
])
def test_normalize(word, expected):
    assert s.normalize(word) == expected


def test_tokenize_drops_stopwords_and_normalizes():
    assert s.tokenize("Why did Intel report write-downs of inventories?") == \
        ["intel", "write", "down", "inventory"]


# --- BM25: primer iz objasnjenja ------------------------------------------------

DOCS = {
    "D1": "Revenue decreased due to lower average selling prices for DRAM and NAND products.",
    "D2": "We recorded inventory write-downs of $1.83 billion due to the challenging pricing environment.",
    "D3": "We hold inventory in many facilities and we review inventory levels, inventory policies "
          "and inventory controls every year as part of our normal operations and planning.",
    "D4": "Gross margin decreased primarily due to lower prices and charges to write down inventories.",
}


def test_bm25_beats_naive_counting():
    """D3 ima najvise pogodaka reci 'inventory', ali D2 je pravi odgovor."""
    names = list(DOCS)
    bm25 = s.BM25([s.tokenize(t) for t in DOCS.values()])
    ranked = [names[i] for i, _ in bm25.top(s.tokenize("inventory write-downs"), k=4)]
    assert ranked[0] == "D2"
    assert "D1" not in ranked                     # bez ijedne reci iz upita -> nije u rezultatima
    assert ranked.index("D2") < ranked.index("D3")


def test_bm25_rare_terms_weigh_more():
    """'due' je u 3 pasusa, 'lower' u 2, 'nand' u 1 -> sto redja rec, to veci IDF.
    ('inventory' je u 3, jer normalizacija pretvara 'inventories' iz D4 u 'inventory'.)"""
    bm25 = s.BM25([s.tokenize(t) for t in DOCS.values()])
    assert bm25.idf["due"] < bm25.idf["lower"] < bm25.idf["nand"]
    assert bm25.idf["inventory"] == bm25.idf["due"]


# --- seckanje ------------------------------------------------------------------

def test_chunk_text_sections_windows_and_headers():
    long_paragraph = " ".join(f"word{i}" for i in range(400))
    text = "\n".join([
        "Table of Contents", "Industry Conditions", "Table of Contents",
        long_paragraph,
        "Table of Contents",
        "Revenue | 100 | 200 |",          # red tabele -> preskace se
        "Restructuring",
        "We recognized restructuring charges of $2.8 billion in 2024 as part of the plan.",
    ])
    passages = s.chunk_text(text)
    sections = [p.section for p in passages]
    assert "Table of Contents" not in sections        # zaglavlje strane, nije sekcija
    assert sections.count("Industry Conditions") == 4  # 400 reci -> prozori od 150, korak 110
    assert passages[-1].section == "Restructuring"
    first, second = passages[0].text.split(), passages[1].text.split()
    assert first[-40:] == second[:40]                  # preklapanje od 40 reci
    assert not any("|" in p.text for p in passages)


def test_risk_sections_are_down_weighted():
    assert s._section_weight("Risks Related to Our Business, Operations, and Industry") == 0.5
    assert s._section_weight("Industry Conditions") == 1.0


# --- integracija nad pravim izvestajima --------------------------------------

needs_data = pytest.mark.skipif(
    not (s.FILINGS_DIR / "manifest.json").exists(), reason="nema podataka - pokreni scripts/download_data.py"
)


def top_text(ticker, year, query, k=3):
    return " ".join(r["text"] for r in s.search_filing(ticker, year, query, top_k=k)["results"])


@needs_data
def test_e1_intel_tax_valuation_allowance():
    assert "$9.9 billion" in top_text("INTC", 2024, "valuation allowance deferred tax assets")


@needs_data
def test_e1_intel_restructuring_and_impairments():
    text = top_text("INTC", 2024, "2024 results impacted by charges impairment restructuring")
    assert "$2.8 billion" in text or "$3.3 billion" in text


@needs_data
def test_e2_nvidia_data_center():
    text = top_text("NVDA", 2024, "data center revenue growth")
    assert "217%" in text or "Hopper" in text


@needs_data
def test_e3_micron_industry_conditions_first():
    result = s.search_filing("MU", 2023, "why loss weak demand pricing")["results"][0]
    assert result["section"] == "Industry Conditions"
    assert "weak demand" in result["text"]


@needs_data
def test_e3_micron_inventory_write_downs():
    assert "write-down" in top_text("MU", 2023, "inventory write-downs")


@needs_data
def test_source_id_matches_financials():
    """Broj i tekst moraju imati isti source_id, da bi sintetizator mogao da ih poveze."""
    hit = s.search_filing("INTC", 2024, "restructuring")
    fin = get_financials("INTC", ["revenue"], [2024])["results"][0]
    assert hit["source_id"] == fin["source_id"] == "INTC-10K-FY2024"
    assert hit["results"][0]["passage_id"].startswith("INTC-10K-FY2024#p")


@needs_data
def test_errors_are_messages():
    assert "Unknown ticker" in s.search_filing("AAPL", 2024, "revenue")["error"]
    assert "No 10-K" in s.search_filing("INTC", 2019, "revenue")["error"]
    assert "no searchable words" in s.search_filing("INTC", 2024, "why did the")["error"]

"""Testovi automatskih metrika evala (bez modela)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from metrics import check_citations, cost_usd, extract_citations, stability  # noqa: E402

from agents.single_agent import returned_ids  # noqa: E402


def test_returned_ids_from_financials_and_search():
    fin = '{"ticker":"INTC","results":[{"fiscal_year":2024,"source_id":"INTC-10K-FY2024","revenue":53.101}]}'
    search = ('{"source_id":"MU-10K-FY2023","results":[{"passage_id":"MU-10K-FY2023#p221"},'
              '{"passage_id":"MU-10K-FY2023#p231"}]}')
    assert returned_ids(fin) == ["INTC-10K-FY2024"]
    assert returned_ids(search) == ["MU-10K-FY2023", "MU-10K-FY2023#p221", "MU-10K-FY2023#p231"]
    assert returned_ids("Error: unknown metric") == []


@pytest.mark.parametrize("answer, expected", [
    ("Revenue $53.101B [INTC-10K-FY2024].", ["INTC-10K-FY2024"]),
    ("[HD-10K-FY2023][HD-10K-FY2024]", ["HD-10K-FY2023", "HD-10K-FY2024"]),
    ("savings [MU-10K-FY2023#p223, #p227]", ["MU-10K-FY2023#p223", "MU-10K-FY2023#p227"]),
    ("[ADBE-10K-FY2025, CRM-10K-FY2025]", ["ADBE-10K-FY2025", "CRM-10K-FY2025"]),
    ("only through FY2025 [INTC], no estimate", ["INTC"]),          # neispravan pokusaj citata
    ("returned no results [t1].", ["t1"]),                          # ID podzadatka nije izvor
    ("see the table [1] and [note]", []),                           # nije citat
    (None, []),
])
def test_extract_citations(answer, expected):
    assert extract_citations(answer) == expected


def test_citation_valid_only_if_returned_in_same_run():
    returned = {"INTC-10K-FY2024", "MU-10K-FY2023", "MU-10K-FY2023#p221"}
    result = check_citations("A [INTC-10K-FY2024]. B [MU-10K-FY2023#p221, #p999]. C [INTC].", returned)
    assert result == {"citations": 4, "valid": 2, "invalid": ["MU-10K-FY2023#p999", "INTC"]}


def test_cost_and_stability():
    assert cost_usd(1_000_000, 1_000_000) == pytest.approx(0.375)
    assert stability({"F1": [1, 1, 1], "C4": [0, 1, 0], "E1": [0.5]}) == 0.5   # E1 ima 1 pokretanje

"""Pretraga teksta 10-K izvestaja pomocu BM25 (pisano rucno, bez biblioteka).

Tok:
  1. chunk_text: 10-K tekst -> prozori od ~150 reci (sa preklapanjem), svaki sa nazivom sekcije
  2. tokenize:   pasus -> lista normalizovanih reci ("Inventories" -> "inventory")
  3. BM25:       za upit racuna skor svakog pasusa i vraca najbolje

Formula (za pasus D i reci upita q):
    score(D) = sum_q  IDF(q) * f(q,D) * (k1 + 1) / (f(q,D) + k1 * (1 - b + b * |D| / avgdl))
    IDF(q)   = ln((N - n(q) + 0.5) / (n(q) + 0.5) + 1)
"""
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from mcp_server.companies import COMPANIES

FILINGS_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "filings"

# --- 1. tokenizacija -------------------------------------------------------------

# Ceste reci koje nose malo znacenja. IDF bi ih i sam oslabio, ali iz upita poput
# "Why did Intel report a loss" samo prave sum, pa ih izbacujemo.
STOPWORDS = set("""
a an and are as at be been by did do does for from had has have how in into is it its
of on or our that the their there these this to was we were what when which while who
why will with according report reported company
""".split())


def normalize(word: str) -> str:
    """Laka normalizacija mnozine, da 'inventories' i 'inventory' budu ista rec.
    Namerno jednostavno: dosledno primenjeno na tekst i upit, pa greske ne smetaju."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"                      # inventories -> inventory
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]                            # taxes -> tax
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]                            # downs -> down, prices -> price
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [normalize(w) for w in words if w not in STOPWORDS]


# --- 2. seckanje teksta na pasuse ------------------------------------------------

@dataclass(frozen=True)
class Passage:
    section: str
    text: str


WINDOW_WORDS = 150   # velicina prozora (pasusa) u recima
WINDOW_STEP = 110    # pomeraj -> 40 reci preklapanja izmedju susednih prozora


def _is_table_row(line: str) -> bool:
    return line.count("|") >= 2


def _is_heading(line: str) -> bool:
    """Podnaslov: kratka linija, nije tabela, ne zavrsava se interpunkcijom, pocinje slovom.
    Dvotacka iskljucuje uvodne recenice tipa '...were as follows:'."""
    words = line.split()
    return (0 < len(words) <= 12 and not _is_table_row(line)
            and not line.rstrip().endswith((".", ";", ",", ":"))
            and line.lstrip()[:1].isalpha())


def _windows(words: list[str]):
    """Prozori sa preklapanjem: recenica na granici prozora je cela u bar jednom od njih."""
    for start in range(0, len(words), WINDOW_STEP):
        yield " ".join(words[start:start + WINDOW_WORDS])
        if start + WINDOW_WORDS >= len(words):
            break


def chunk_text(text: str) -> list[Passage]:
    """Tekst se deli po sekcijama (podnaslovima), a svaka sekcija na prozore od ~150 reci."""
    passages: list[Passage] = []
    section = "Unknown section"
    buffer: list[str] = []   # reci tekuce sekcije

    def flush():
        if buffer:
            passages.extend(Passage(section, w) for w in _windows(buffer))
            buffer.clear()

    lines = [raw.strip(" |\t") for raw in text.splitlines()]
    # Zaglavlja strana ("Table of Contents", ime kompanije...) ponavljaju se na svakoj strani;
    # nisu pravi podnaslovi, pa ih preskacemo.
    counts = Counter(lines)
    running_headers = {ln for ln, c in counts.items() if c >= 3 and _is_heading(ln)}

    for line in lines:
        if not line or _is_table_row(line) or line in running_headers:
            continue
        if _is_heading(line):
            flush()                      # novi podnaslov zatvara prethodni pasus
            section = line.rstrip(": ")
            continue
        words = line.split()
        if len(words) < 8:               # ostaci (brojevi strana, fusnote) - preskoci
            continue
        buffer.extend(words)
    flush()
    return passages


# --- 3. BM25 -------------------------------------------------------------------

class BM25:
    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(d) for d in documents]       # f(q, D) za svaki pasus
        self.lengths = [len(d) for d in documents]        # |D|
        self.avgdl = sum(self.lengths) / len(documents) if documents else 0.0
        self.n_docs = len(documents)                      # N
        df = Counter(term for d in documents for term in set(d))  # n(q)
        self.idf = {t: math.log((self.n_docs - n + 0.5) / (n + 0.5) + 1) for t, n in df.items()}

    def score(self, query: list[str], i: int) -> float:
        tf, length, total = self.docs[i], self.lengths[i], 0.0
        for term in query:
            f = tf.get(term, 0)
            if f == 0:
                continue
            norm = self.k1 * (1 - self.b + self.b * length / self.avgdl)
            total += self.idf[term] * f * (self.k1 + 1) / (f + norm)
        return total

    def top(self, query: list[str], k: int, weights: list[float] | None = None) -> list[tuple[int, float]]:
        """Najboljih k pasusa. `weights` opciono mnozi skor pojedinih pasusa."""
        scored = [(i, self.score(query, i) * (weights[i] if weights else 1.0)) for i in range(self.n_docs)]
        scored = [s for s in scored if s[1] > 0]
        return sorted(scored, key=lambda s: s[1], reverse=True)[:k]


# Risk Factors opisuju sta MOZE da se desi (sablonski tekst pun istih reci), a nasa pitanja
# su "sta se desilo i zasto" - zato im spustamo prioritet, ali ih ne izbacujemo.
RISK_SECTION_WEIGHT = 0.5


def _section_weight(section: str) -> float:
    s = section.lower()
    return RISK_SECTION_WEIGHT if ("risk factor" in s or s.startswith("risks related")) else 1.0


# --- 4. indeks po izvestaju i alat ---------------------------------------------

@lru_cache(maxsize=1)
def _manifest() -> dict:
    return json.loads((FILINGS_DIR / "manifest.json").read_text(encoding="utf-8"))


def _filing_for(ticker: str, fiscal_year: int) -> dict | None:
    for key, meta in _manifest().items():
        if meta["ticker"] == ticker and meta["fiscal_year"] == fiscal_year:
            return {"key": key, **meta}
    return None


@lru_cache(maxsize=32)
def _index(key: str) -> tuple[list[Passage], BM25, list[float]]:
    """Seckanje i indeks se prave jednom po izvestaju, posle su u memoriji."""
    passages = chunk_text((FILINGS_DIR / f"{key}.txt").read_text(encoding="utf-8"))
    bm25 = BM25([tokenize(p.section + " " + p.text) for p in passages])
    return passages, bm25, [_section_weight(p.section) for p in passages]


def search_filing(ticker: str, fiscal_year: int, query: str, top_k: int = 3) -> dict:
    ticker = ticker.upper().strip()
    if ticker not in COMPANIES:
        return {"error": f"Unknown ticker '{ticker}'. Available: {', '.join(COMPANIES)}"}
    filing = _filing_for(ticker, fiscal_year)
    if filing is None:
        years = sorted(m["fiscal_year"] for m in _manifest().values() if m["ticker"] == ticker)
        return {"error": f"No 10-K for {ticker} fiscal year {fiscal_year}. Available: {years}"}

    query_tokens = tokenize(query)
    if not query_tokens:
        return {"error": "Query has no searchable words. Use specific terms, e.g. 'inventory write-down'."}

    passages, bm25, weights = _index(filing["key"])
    source_id = f"{ticker}-10K-FY{fiscal_year}"   # isti format kao u financials.py
    hits = bm25.top(query_tokens, top_k, weights)
    return {
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "source_id": source_id,
        "filing": {"period_end": filing["period_end"], "filed": filing["filed"], "url": filing["url"]},
        "results": [
            {"passage_id": f"{source_id}#p{i}", "section": passages[i].section,
             "score": round(score, 2), "text": passages[i].text}
            for i, score in hits
        ],
        **({} if hits else {"note": "No matching passages. Try different or more specific words."}),
    }

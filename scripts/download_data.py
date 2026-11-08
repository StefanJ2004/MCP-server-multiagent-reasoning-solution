"""Skida sirove podatke za sve kompanije u data/raw/.

- data/raw/companyfacts/{TICKER}.json   XBRL brojevi (sve metrike, svi periodi)
- data/raw/filings/{TICKER}_{period_end}.txt   tekst 10-K izvestaja (HTML -> tekst)
- data/raw/filings/manifest.json   metapodaci o svakom 10-K (za citate)

Pokretanje (iz root foldera):  python scripts/download_data.py
Vec skinuti fajlovi se preskacu, pa se skripta moze bezbedno ponovo pokrenuti.
"""
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mcp_server.companies import COMPANIES, FIRST_FISCAL_YEAR  # noqa: E402

RAW = ROOT / "data" / "raw"
FACTS_DIR = RAW / "companyfacts"
FILINGS_DIR = RAW / "filings"

load_dotenv(ROOT / ".env")
USER_AGENT = os.environ.get("SEC_USER_AGENT", "").strip()


def get(url: str) -> bytes:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            time.sleep(0.2)  # SEC limit je 10 zahteva/s
            return data
        except Exception as e:
            print(f"   pokusaj {attempt + 1} nije uspeo: {e}", flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Ne mogu da skinem {url}")


class _HtmlToText(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "ix:header"):
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "ix:header"):
            self.skip -= 1
        if tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _HtmlToText()
    p.feed(html)
    text = re.sub(r"[ \t\xa0]+", " ", "".join(p.parts))
    return re.sub(r"\n\s*\n+", "\n", text)


def main() -> None:
    if not USER_AGENT:
        sys.exit("Postavi SEC_USER_AGENT u .env (npr. 'Ime Prezime email@domen.com').")
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    FILINGS_DIR.mkdir(parents=True, exist_ok=True)

    tickers = {v["ticker"]: v["cik_str"]
               for v in json.loads(get("https://www.sec.gov/files/company_tickers.json")).values()}

    manifest_path = FILINGS_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    for ticker in COMPANIES:
        cik = tickers[ticker]
        facts_path = FACTS_DIR / f"{ticker}.json"
        if not facts_path.exists():
            print(f"{ticker}: companyfacts", flush=True)
            facts_path.write_bytes(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"))

        for recent in submission_pages(cik):
            download_10ks(ticker, cik, recent, manifest)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Gotovo: {len(list(FACTS_DIR.glob('*.json')))} companyfacts, {len(manifest)} 10-K izvestaja.")


def submission_pages(cik: int):
    """Spisak prijava kompanije. API u 'recent' vraca samo ~1000 poslednjih prijava;
    starije su u dodatnim fajlovima (filings.files) - bez njih nam fale stari 10-K."""
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    yield sub["filings"]["recent"]
    for extra in sub["filings"].get("files", []):
        if extra.get("filingTo", "9999") >= f"{FIRST_FISCAL_YEAR}-01-01":
            yield json.loads(get(f"https://data.sec.gov/submissions/{extra['name']}"))


def download_10ks(ticker: str, cik: int, page: dict, manifest: dict) -> None:
    for i, form in enumerate(page["form"]):
        period_end = page["reportDate"][i]
        if form != "10-K" or not period_end or int(period_end[:4]) < FIRST_FISCAL_YEAR:
            continue
        key = f"{ticker}_{period_end}"
        out = FILINGS_DIR / f"{key}.txt"
        accn = page["accessionNumber"][i]
        doc = page["primaryDocument"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}"
        if not out.exists():
            print(f"{ticker}: 10-K {period_end}", flush=True)
            out.write_text(html_to_text(get(url).decode("utf-8", errors="replace")), encoding="utf-8")
        manifest[key] = {
            "ticker": ticker,
            "period_end": period_end,
            "fiscal_year": int(period_end[:4]),  # nasa konvencija: godina zavrsetka
            "filed": page["filingDate"][i],
            "accession": accn,
            "url": url,
        }


if __name__ == "__main__":
    main()

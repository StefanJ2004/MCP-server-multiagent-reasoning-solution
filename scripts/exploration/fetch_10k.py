"""Skida 10-K za dati ticker i datum kraja perioda, cuva kao cist tekst."""
import json, os, re, sys, time, urllib.request
from html.parser import HTMLParser

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "filings")
UA = {"User-Agent": "hakaton-learning-project contact@example.com"}


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.read()
        except Exception as e:
            print(f"   retry {i+1} ({e.__class__.__name__})", flush=True)
            time.sleep(2 * (i + 1))
    raise RuntimeError(url)


class Text(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style") or (tag == "ix:header"):
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") or (tag == "ix:header"):
            self.skip -= 1
        if tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def main(ticker, period_end):
    os.makedirs(OUT, exist_ok=True)
    tickers = json.load(open(os.path.join(BASE, "edgar", "tickers.json")))
    cik = tickers[ticker]
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    rec = sub["filings"]["recent"]
    for i, form in enumerate(rec["form"]):
        if form == "10-K" and rec["reportDate"][i] == period_end:
            accn = rec["accessionNumber"][i].replace("-", "")
            doc = rec["primaryDocument"][i]
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}"
            print(f"{ticker}: 10-K za {period_end}, podnet {rec['filingDate'][i]}, {url}", flush=True)
            p = Text()
            p.feed(get(url).decode("utf-8", errors="replace"))
            text = re.sub(r"[ \t\xa0]+", " ", "".join(p.parts))
            text = re.sub(r"\n\s*\n+", "\n", text)
            path = os.path.join(OUT, f"{ticker}_10K_{period_end}.txt")
            open(path, "w", encoding="utf-8").write(text)
            print(f"   sacuvano {path} ({len(text):,} karaktera)", flush=True)
            return
    print(f"{ticker}: nije nadjen 10-K sa reportDate={period_end}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        t, e = arg.split(":")
        main(t, e)
        time.sleep(0.5)

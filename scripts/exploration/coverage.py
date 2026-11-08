import json, os, sys, time, urllib.request
from datetime import date

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edgar")
UA = {"User-Agent": "hakaton-learning-project contact@example.com"}

TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "rnd": ["ResearchAndDevelopmentExpense",
            "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
            "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost"],
}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print(f"   retry {i+1} ({e.__class__.__name__})", flush=True)
            time.sleep(2 * (i + 1))
    raise RuntimeError(url)


def load(ticker, tickers):
    path = os.path.join(DIR, f"{ticker}.json")
    if ticker == "NVDA" and not os.path.exists(path):
        path = os.path.join(DIR, "nvda.json")
    if not os.path.exists(path):
        d = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{tickers[ticker]:010d}.json")
        json.dump(d, open(path, "w"))
        time.sleep(0.3)
    return json.load(open(path))


def annual_periods(gaap, metric):
    """{end_date: (tag, val)} za godisnje periode iz 10-K, spojeno preko svih tagova."""
    out = {}
    for tag in TAGS[metric]:
        for r in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if r["form"] != "10-K" or "start" not in r:
                continue
            days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
            if days > 350:
                out.setdefault(r["end"], (tag, r["val"]))
    return out


def check(ticker, tickers, need_rnd):
    d = load(ticker, tickers)
    gaap = d["facts"]["us-gaap"]
    metrics = ["revenue", "gross_profit", "operating_income", "net_income"] + (["rnd"] if need_rnd else [])
    res = {}
    for m in metrics:
        per = {e: v for e, v in annual_periods(gaap, m).items() if e >= "2022-01-01"}
        res[m] = (len(per), max(per) if per else None, sorted({t for t, _ in per.values()}))
    ok = all(n >= 4 for n, _, _ in res.values())
    return d["entityName"], ok, res


if __name__ == "__main__":
    tickers = json.load(open(os.path.join(DIR, "tickers.json")))
    groups = json.loads(sys.argv[1])  # {"grupa": [[ticker, need_rnd], ...]}
    for g, items in groups.items():
        print(f"\n### {g}", flush=True)
        for t, need_rnd in items:
            try:
                name, ok, res = check(t, tickers, need_rnd)
            except Exception as e:
                print(f"{t:5} GRESKA {e}", flush=True)
                continue
            gaps = {m: f"{n}g, do {last}" for m, (n, last, _) in res.items() if n < 4}
            alt = {m: tags for m, (_, _, tags) in res.items() if len(tags) > 1 or (tags and tags[0] != TAGS[m][0])}
            print(f"{t:5} {'OK ' if ok else 'NE '} {name[:28]:28} fale={gaps or '-'} alt_tagovi={alt or '-'}", flush=True)

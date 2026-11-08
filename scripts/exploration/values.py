import json, os, sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coverage import TAGS, DIR

METRICS = ["revenue", "gross_profit", "operating_income", "net_income", "rnd"]


def annual_all(gaap, metric):
    """{(start,end): {(tag,val), ...}} - svi zapisi, da vidimo konflikte."""
    out = defaultdict(set)
    for tag in TAGS[metric]:
        for r in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if r["form"] != "10-K" or "start" not in r:
                continue
            if (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days > 350 and r["end"] >= "2022-01-01":
                out[(r["start"], r["end"])].add((tag, r["val"]))
    return out


for t in sys.argv[1:]:
    d = json.load(open(os.path.join(DIR, f"{t}.json")))
    gaap = d["facts"]["us-gaap"]
    data = {m: annual_all(gaap, m) for m in METRICS}
    periods = sorted({p for m in METRICS for p in data[m]}, key=lambda p: p[1])
    print(f"\n### {t} - {d['entityName']}  (milijarde USD)")
    print(f"{'period':25} " + " ".join(f"{m[:12]:>12}" for m in METRICS) + "   bruto% oper% neto%")
    for p in periods:
        row, vals = [], {}
        for m in METRICS:
            entries = data[m].get(p, set())
            distinct = {v for _, v in entries}
            if not distinct:
                row.append(f"{'-':>12}")
                continue
            v = sorted(distinct)[0]
            vals[m] = v
            flag = "!" if len(distinct) > 1 else " "
            row.append(f"{v/1e9:11.3f}{flag}")
        r = vals.get("revenue")
        pct = lambda k: f"{100*vals[k]/r:5.1f}" if r and k in vals else "    -"
        print(f"{p[0]}..{p[1]} " + " ".join(row) + f"   {pct('gross_profit')} {pct('operating_income')} {pct('net_income')}")
    conflicts = [(m, p, sorted(e)) for m in METRICS for p, e in data[m].items() if len({v for _, v in e}) > 1]
    for m, p, e in conflicts:
        print(f"   ! KONFLIKT {m} {p}: {e}")

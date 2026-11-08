"""Izvestaj evala: spaja rezultate, kljuc i ocene i racuna sve metrike po sistemu.

Pokretanje:  python eval/report.py eval/results/<datum_vreme>
Bez grades.json racuna samo automatske metrike (vreme, tokeni, cena, citati...); sa ocenama i tacnost.
Pise report.md u isti folder i stampa ga.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from metrics import check_citations, cost_usd, stability, summary

SYSTEMS = ("single", "multi")


def load(out_dir: Path):
    results = [json.loads(line) for line in (out_dir / "results.jsonl").read_text("utf-8").splitlines() if line]
    grades_path = out_dir / "grades.json"
    if not grades_path.exists():
        return results, False
    key = json.loads((out_dir / "key.json").read_text("utf-8"))
    grades = json.loads(grades_path.read_text("utf-8"))
    by_record = {(k["system"], k["run"], k["question_id"]): grades.get(gid) for gid, k in key.items()}
    for r in results:
        g = by_record.get((r["system"], r["run"], r["question_id"]))
        if g is not None:
            r["score"], r["numbers_ok"], r["grade_reason"] = g["score"], g.get("numbers_ok"), g.get("reason")
    return results, True


def enrich(r: dict, model: str) -> dict:
    """Automatske metrike po odgovoru."""
    returned = {i for c in r.get("tool_calls") or [] for i in c.get("returned_ids", [])}
    cit = check_citations(r["answer"] if r["stop_reason"] == "answer" else None, returned)
    calls = r.get("tool_calls") or []
    return {**r, **{f"cit_{k}": v for k, v in cit.items()},
            "cost": cost_usd(r.get("input_tokens", 0), r.get("output_tokens", 0), model),
            "n_tool_calls": len(calls),
            "n_search": sum(c["name"] == "search_filing" for c in calls),
            "n_financials": sum(c["name"] == "get_financials" for c in calls),
            "n_tool_errors": sum(bool(c.get("error")) for c in calls)}


def fmt(v, digits=1, pct=False):
    if v is None:
        return "-"
    return f"{v * 100:.{digits}f}%" if pct else f"{v:,.{digits}f}"


def system_metrics(rows: list[dict], graded: bool) -> dict:
    m = {"odgovora": len(rows)}
    if graded:
        scored = [r for r in rows if "score" in r]
        for label, subset in [("tačnost: main (12)", [r for r in scored if r["set"] == "main"]),
                              ("tačnost: extra (B1, H1–H3)", [r for r in scored if r["set"] == "extra"]),
                              ("tačnost: sve", scored)]:
            m[label] = fmt(summary([r["score"] for r in subset])["mean"], pct=True)
        nums = [r["numbers_ok"] for r in scored if r.get("numbers_ok") is not None]
        m["brojevi tačni"] = fmt(sum(nums) / len(nums), pct=True) if nums else "-"
        by_q = defaultdict(list)
        for r in scored:
            by_q[r["question_id"]].append(r["score"])
        m["stabilnost (ista ocena u svim pokretanjima)"] = fmt(stability(by_q), pct=True)
        total_cost, total_score = sum(r["cost"] for r in rows), sum(r["score"] for r in scored)
        m["cena po tačnom odgovoru ($)"] = fmt(total_cost / total_score, 5) if total_score else "-"
    t = summary([r["seconds"] for r in rows])
    m["vreme: prosek / medijana / max (s)"] = f"{fmt(t['mean'])} / {fmt(t['median'])} / {fmt(t['max'])}"
    m["ulazni tokeni (prosek)"] = fmt(summary([r.get("input_tokens") for r in rows])["mean"], 0)
    m["izlazni tokeni (prosek)"] = fmt(summary([r.get("output_tokens") for r in rows])["mean"], 0)
    m["najveći kontekst u 1 pozivu: prosek / max"] = (
        f"{fmt(summary([r.get('max_input_tokens') for r in rows])['mean'], 0)} / "
        f"{fmt(summary([r.get('max_input_tokens') for r in rows])['max'], 0)}")
    m["cena po pitanju (prosek, $)"] = fmt(summary([r["cost"] for r in rows])["mean"], 5)
    m["cena ukupno ($)"] = fmt(sum(r["cost"] for r in rows), 4)
    m["pozivi modela (prosek)"] = fmt(summary([r.get("llm_calls") for r in rows])["mean"])
    m["pozivi alata (prosek): ukupno / financials / search"] = (
        f"{fmt(summary([r['n_tool_calls'] for r in rows])['mean'])} / "
        f"{fmt(summary([r['n_financials'] for r in rows])['mean'])} / "
        f"{fmt(summary([r['n_search'] for r in rows])['mean'])}")
    m["greške alata (ukupno, model se ispravlja)"] = sum(r["n_tool_errors"] for r in rows)
    cits, valid = sum(r["cit_citations"] for r in rows), sum(r["cit_valid"] for r in rows)
    m["citati: važeći / ukupno"] = f"{valid} / {cits} ({fmt(valid / cits, pct=True) if cits else '-'})"
    m["odgovori sa bar jednim nevažećim citatom"] = sum(bool(r["cit_invalid"]) for r in rows)
    m["odgovori bez ijednog citata"] = sum(r["cit_citations"] == 0 for r in rows if r["stop_reason"] == "answer")
    m["razlozi zaustavljanja"] = ", ".join(f"{k}: {v}" for k, v in Counter(r["stop_reason"] for r in rows).items())
    multi = [r for r in rows if r["system"] == "multi"]
    if multi:
        m["rezervni plan (planer nije uspeo)"] = sum(bool(r.get("plan_fallback")) for r in multi)
        m["podzadataka po pitanju (prosek)"] = fmt(summary([len(r.get("plan") or []) for r in multi])["mean"])
        speedups = [sum(f["seconds"] for f in r["findings"]) / r["research_seconds"]
                    for r in multi if r.get("findings") and r.get("research_seconds")]
        m["ubrzanje od paralelizma (zbir vremena istraživača / trajanje faze)"] = \
            f"{fmt(summary(speedups)['mean'], 2)}×"
    return m


def per_question_table(rows: list[dict], graded: bool) -> list[str]:
    lines = ["| Pitanje | Tip | " + " | ".join(f"{s}: ocene" if graded else f"{s}: s" for s in SYSTEMS) +
             " | " + " | ".join(f"{s}: tokena (ulaz)" for s in SYSTEMS) + " |",
             "|---|---|" + "---|" * (2 * len(SYSTEMS))]
    by = defaultdict(list)
    for r in rows:
        by[(r["question_id"], r["system"])].append(r)
    for qid in dict.fromkeys(r["question_id"] for r in rows):
        cells = []
        for s in SYSTEMS:
            rs = sorted(by[(qid, s)], key=lambda r: r["run"])
            cells.append(" ".join(fmt(r.get("score"), 1) if graded else fmt(r["seconds"]) for r in rs) or "-")
        tokens = [fmt(summary([r.get("input_tokens") for r in by[(qid, s)]])["mean"], 0) for s in SYSTEMS]
        qtype = next(r["type"] for r in rows if r["question_id"] == qid)
        lines.append(f"| {qid} | {qtype} | " + " | ".join(cells) + " | " + " | ".join(tokens) + " |")
    return lines


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else sys.exit("Upotreba: python eval/report.py <folder>")
    results, graded = load(out_dir)
    config = json.loads((out_dir / "config.json").read_text("utf-8"))
    rows = [enrich(r, config["model"]) for r in results]
    per_system = {s: system_metrics([r for r in rows if r["system"] == s], graded) for s in SYSTEMS}

    lines = [f"# Eval izveštaj: {out_dir.name}", "",
             f"Model: `{config['model']}`, provajder(i): "
             f"{', '.join(sorted({p for r in rows for p in r.get('providers', [])}))}; "
             f"modeli u odgovorima: {', '.join(sorted({m for r in rows for m in r.get('models', [])}))}; "
             f"pokretanja: {config['runs']}.", "",
             "Ocenjivanje: " + ("Claude, naslepo (to_grade.json bez oznake sistema), po pravilima iz "
                                "questions.json; 1 / 0,5 / 0." if graded else "**još nema ocena** (grades.json)."),
             "Cena je gornja granica (cena zakucanog provajdera iz eval/metrics.py, bez popusta za keširan ulaz).", "",
             "## Po sistemu", "", "| Metrika | Jedan agent | Multi-agent |", "|---|---|---|"]
    metric_order = list(dict.fromkeys(list(per_system["single"]) + list(per_system["multi"])))
    for metric in metric_order:
        lines.append(f"| {metric} | {per_system['single'].get(metric, '-')} | {per_system['multi'].get(metric, '-')} |")
    lines += ["", "## Po pitanju", ""] + per_question_table(rows, graded)
    invalid = [(r["system"], r["run"], r["question_id"], r["cit_invalid"]) for r in rows if r["cit_invalid"]]
    if invalid:
        lines += ["", "## Nevažeći citati", ""] + [f"- {s} run {n} {q}: {', '.join(c)}" for s, n, q, c in invalid]
    report = "\n".join(lines) + "\n"
    (out_dir / "report.md").write_text(report, "utf-8")
    print(report)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

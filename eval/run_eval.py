"""Eval: jedan agent i multi-agent na istim pitanjima, vise pokretanja; cuva pun trag svakog odgovora
i pravi fajlove za ocenjivanje NASLEPO.

Fer poredjenje: isti model, ista podesavanja (.env, thinking iskljucen), ista MCP veza.
Pitanja idu redom, a sistemi naizmenicno (jednom prvi single, jednom multi), da nijedan sistem
ne bude uvek prvi (npr. kad se index pretrage tek ucitava ili je provajder sporiji).

Pokretanje:
  python eval/run_eval.py                          # sva pitanja x 2 sistema x 3 pokretanja
  python eval/run_eval.py --runs 1 --ids F1 C4     # brza proba
  python eval/run_eval.py --out eval/results/X     # nastavak prekinutog: preskace vec gotove odgovore

Izlaz u eval/results/<datum_vreme>/:
  results.jsonl   jedan red po odgovoru: odgovor, tokeni, vreme, pozivi alata, pun trag dogadjaja
  to_grade.json   odgovori izmesani i anonimni (g001, g002...), sa pravilima ocenjivanja iz pitanja
  key.json        koji g### je koji sistem i pokretanje - NE otvarati pre ocenjivanja
Zatim: ocene u grades.json, pa  python eval/report.py eval/results/<datum_vreme>
"""
import argparse
import asyncio
import json
import os
import random
import sys
import zlib
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp import Client, StdioServerParameters
from openai import AsyncOpenAI

from agents.multi_agent import run_multi_agent
from agents.single_agent import LLM_TIMEOUT_SECONDS, provider_options, run_agent

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = ("single", "multi")
RUBRIC_SKIP = {"id", "question", "question_en", "set", "verified"}   # sve ostalo iz pitanja ide ocenjivacu


async def run_one(system: str, question: str, llm, mcp, model: str, extra_body: dict) -> dict:
    """Jedno pitanje, jedan sistem. Pad (npr. greska API-ja) se belezi kao rezultat, eval ide dalje."""
    events = []
    started = time.perf_counter()

    def on_event(event, **data):
        events.append({"t": round(time.perf_counter() - started, 2), "event": event, **data})

    try:
        if system == "single":
            r = await run_agent(question, llm, mcp, model, extra_body=extra_body, on_event=on_event)
            record = {"answer": r.answer, "stop_reason": r.stop_reason, "seconds": r.seconds,
                      "llm_calls": r.steps, "tool_calls": r.tool_calls, "input_tokens": r.input_tokens,
                      "output_tokens": r.output_tokens, "max_input_tokens": r.max_input_tokens}
        else:
            r = await run_multi_agent(question, llm, mcp, model, extra_body=extra_body, on_event=on_event)
            record = {"answer": r.answer, "stop_reason": r.stop_reason, "seconds": r.seconds,
                      "llm_calls": r.llm_calls, "tool_calls": [c for f in r.findings for c in f["tool_calls"]],
                      "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                      "max_input_tokens": r.max_input_tokens, "plan": r.plan, "plan_fallback": r.plan_fallback,
                      "research_seconds": r.research_seconds,
                      "findings": [{k: v for k, v in f.items() if k != "tool_calls"} for f in r.findings]}
    except Exception as e:
        record = {"answer": None, "stop_reason": f"exception: {e!r}",
                  "seconds": round(time.perf_counter() - started, 1)}
    record["models"] = sorted({str(e["model"]) for e in events if e.get("model")})
    record["providers"] = sorted({str(e["provider"]) for e in events if e.get("provider")})
    record["events"] = events
    return record


def load_questions(ids: list[str] | None) -> list[dict]:
    questions = json.loads((ROOT / "eval" / "questions.json").read_text("utf-8"))["questions"]
    if ids:
        unknown = set(ids) - {q["id"] for q in questions}
        if unknown:
            sys.exit(f"Nepoznata pitanja: {sorted(unknown)}")
        questions = [q for q in questions if q["id"] in ids]
    return questions


def read_results(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def make_grading_files(out_dir: Path) -> None:
    """to_grade.json (anonimno, izmesano) + key.json (ko je ko). Ne dira ih ako ocene vec postoje."""
    if (out_dir / "grades.json").exists():
        print("grades.json vec postoji - to_grade.json i key.json se ne menjaju.")
        return
    by_id = {q["id"]: q for q in load_questions(None)}   # sva pitanja, i kod nastavka sa drugim --ids
    records = read_results(out_dir / "results.jsonl")
    # Seme zavisi od foldera: svaki eval ima drugaciji raspored g###, pa ocenjivac iz ranijeg evala
    # ne moze da zna koji ID je koji sistem (u evalu 2026-11-08_1949 seme je bilo isto kao u _1903).
    random.Random(zlib.crc32(out_dir.name.encode())).shuffle(records)
    to_grade, key = [], {}
    for i, r in enumerate(records, start=1):
        grade_id = f"g{i:03d}"
        q = by_id[r["question_id"]]
        valid = r["stop_reason"] == "answer"
        to_grade.append({
            "grade_id": grade_id, "question_id": q["id"], "type": q["type"], "question_en": q["question_en"],
            "rubric": {k: v for k, v in q.items() if k not in RUBRIC_SKIP},
            "status": "answer" if valid else f"NO VALID ANSWER ({r['stop_reason']}) - score 0",
            "answer": r["answer"] if valid else None})
        key[grade_id] = {"system": r["system"], "run": r["run"], "question_id": q["id"]}
    (out_dir / "to_grade.json").write_text(json.dumps(to_grade, ensure_ascii=False, indent=1), "utf-8")
    (out_dir / "key.json").write_text(json.dumps(key, indent=1), "utf-8")
    print(f"Za ocenjivanje: {out_dir / 'to_grade.json'} ({len(to_grade)} odgovora)")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Eval: jedan agent naspram multi-agenta")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--ids", nargs="*", help="samo ova pitanja, npr. F1 C4")
    parser.add_argument("--out", help="folder rezultata (postojeci = nastavak)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    model, extra_body = os.environ["MODEL"], provider_options()
    questions = load_questions(args.ids)
    out_dir = Path(args.out) if args.out else ROOT / "eval" / "results" / datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    done = {(r["system"], r["run"], r["question_id"]) for r in read_results(results_path)}

    config = {"model": model, "base_url": os.environ.get("OPENAI_BASE_URL"), "extra_body": extra_body,
              "runs": args.runs, "questions": [q["id"] for q in questions], "started": datetime.now().isoformat()}
    (out_dir / "config.json").write_text(json.dumps(config, indent=1), "utf-8")
    total = args.runs * len(questions) * len(SYSTEMS)
    print(f"Eval -> {out_dir}  ({total} odgovora, {len(done)} vec gotovo)\n", flush=True)

    llm = AsyncOpenAI(timeout=LLM_TIMEOUT_SECONDS)
    server = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT))
    async with Client(server) as mcp:
        for run in range(1, args.runs + 1):
            for qi, q in enumerate(questions):
                order = SYSTEMS if (run + qi) % 2 == 0 else SYSTEMS[::-1]   # naizmenicno ko ide prvi
                for system in order:
                    if (system, run, q["id"]) in done:
                        continue
                    record = await run_one(system, q["question_en"], llm, mcp, model, extra_body)
                    record = {"system": system, "run": run, "question_id": q["id"], "set": q.get("set", "main"),
                              "type": q["type"], **record}
                    with results_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    done.add((system, run, q["id"]))
                    print(f"[{len(done)}/{total}] run {run} {q['id']:3} {system:6} -> {record['stop_reason']:12} "
                          f"{record['seconds']:5} s  tokena {record.get('input_tokens', 0)}/"
                          f"{record.get('output_tokens', 0)}", flush=True)

    make_grading_files(out_dir)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())

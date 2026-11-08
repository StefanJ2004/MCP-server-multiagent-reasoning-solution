"""Benchmark lokalnog modela preko Ollama: koliko brzo OVAJ racunar radi ono sto ce agent raditi.

Meri:
  1. ucitavanje modela
  2. generisanje (tokena/s)  - model pise odgovor ili poziv alata
  3. prefill (tokena/s)      - model "cita" ulaz: system prompt + seme alata + rezultati alata
                               (kod agenta je ulaz mnogo duzi od izlaza -> verovatno usko grlo)
  4. num_ctx 8192 vs 16384   - memorija i brzina
  5. broj niti i paralelni zahtevi - da li 2 istrazivaca istovremeno idu brze na CPU-u
  6. thinking ukljucen/iskljucen + da li model pravilno zove NASE MCP alate (pitanja iz evala)

Koristi Ollama native API (/api/chat) jer vraca tacna merenja (prompt_eval_duration, eval_duration).
Agent ce kasnije ici preko OpenAI-kompatibilnog endpointa, ali model i brzina su isti.

Pokretanje (Ollama mora da radi, model skinut):
    python scripts/benchmark_ollama.py            # pun, ~10-20 min na laptop CPU-u
    python scripts/benchmark_ollama.py --quick    # samo osnovno, ~3-5 min
Rezultat se cuva u data/benchmark/.  Laptop: ukljuci punjac (na bateriji CPU uspori).
"""
import argparse
import asyncio
import json
import os
import platform
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
NS = 1e9


# --- poziv Ollama-e i merenja ------------------------------------------------------

def ollama(path, payload=None, timeout=1800):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(OLLAMA + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def chat(model, messages, *, num_ctx=8192, num_predict=128, think=False, tools=None,
         temperature=0.0, extra_options=None):
    options = {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": temperature, "seed": 42}
    options.update(extra_options or {})
    payload = {"model": model, "messages": messages, "stream": False, "think": think,
               "options": options, "keep_alive": "15m"}
    if tools:
        payload["tools"] = tools
    t0 = time.perf_counter()
    r = ollama("/api/chat", payload)
    r["wall_s"] = time.perf_counter() - t0
    return r


def measure(r):
    """Iz Ollama odgovora izvuci brojke. Trajanja su u nanosekundama."""
    pc, pd = r.get("prompt_eval_count", 0), r.get("prompt_eval_duration", 0)
    ec, ed = r.get("eval_count", 0), r.get("eval_duration", 0)
    return {
        "prompt_tokens": pc,
        "prefill_tps": round(pc / (pd / NS), 1) if pd else None,
        "output_tokens": ec,
        "gen_tps": round(ec / (ed / NS), 1) if ed else None,
        "load_s": round(r.get("load_duration", 0) / NS, 2),
        "wall_s": round(r["wall_s"], 1),
    }


def nonce():
    """Ollama pamti (kesira) obradjen pocetak prompta. Za merenje prefill-a pocetak mora biti nov."""
    return f"[run {uuid.uuid4().hex[:8]}] "


def unload(model):
    ollama("/api/generate", {"model": model, "keep_alive": 0})


def loaded_memory_gb(model):
    for m in ollama("/api/ps").get("models", []):
        if m["name"].startswith(model):
            return round(m["size"] / 2**30, 2)
    return None


GEN_PROMPT = ("Write a detailed explanation of how a semiconductor company's gross margin can change "
              "from one year to the next. Cover pricing, inventory write-downs, product mix and "
              "factory utilization.")


def gen_test(model, **kw):
    msgs = [{"role": "user", "content": nonce() + GEN_PROMPT}]
    return measure(chat(model, msgs, num_predict=200, **kw))


# --- realan ulaz: pravi rezultati nasih alata ------------------------------------------

SEARCHES = [
    ("MU", 2023, "weak demand pricing"), ("INTC", 2024, "restructuring impairment charges"),
    ("NVDA", 2024, "data center revenue"), ("MU", 2023, "inventory write-downs"),
    ("INTC", 2024, "valuation allowance deferred tax"), ("AMD", 2024, "data center segment"),
    ("HD", 2025, "comparable sales"), ("ADBE", 2025, "operating expenses"),
    ("CRM", 2025, "subscription revenue"), ("LOW", 2024, "net earnings"),
]


def tool_results_context(target_tokens):
    """Spoji JSON rezultate search_filing-a dok ne dobijemo ~target_tokens (proc. 3,6 znaka po tokenu)."""
    from mcp_server.search import search_filing
    from mcp_server.server import _to_json
    parts, chars = [], 0
    for ticker, fy, q in SEARCHES * 3:
        part = _to_json(search_filing(ticker, fy, q))
        parts.append(part)
        chars += len(part)
        if chars >= target_tokens * 3.6:
            break
    return "\n".join(parts)


def prefill_test(model, target_tokens, num_ctx=8192):
    content = (nonce() + "Tool results:\n" + tool_results_context(target_tokens)
               + "\n\nIn one sentence: which company is mentioned first?")
    return measure(chat(model, [{"role": "user", "content": content}], num_ctx=num_ctx, num_predict=24))


# --- nasi MCP alati u formatu koji model razume -----------------------------------------

async def _mcp_tools():
    from mcp import Client
    from mcp_server.server import server
    async with Client(server) as c:
        tools = (await c.list_tools()).tools
    # MCP sema (name, description, inputSchema) -> OpenAI/Ollama "function" format.
    # Ovo isto preslikavanje ce raditi agent u fazi 2.
    return [{"type": "function",
             "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
            for t in tools]


SYSTEM = ("You are a financial research assistant. Answer using the tools. "
          "Use get_financials for numbers and search_filing for explanations. "
          "Never invent numbers. Cite source_id or passage_id.")

TOOL_QUESTIONS = ["F1", "C2", "E3"]


def tool_call_test(model, tools, think):
    questions = {q["id"]: q for q in json.loads((ROOT / "eval/questions.json").read_text("utf-8"))["questions"]}
    out = []
    for qid in TOOL_QUESTIONS:
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": questions[qid]["question_en"]}]
        r = chat(model, msgs, tools=tools, think=think, num_predict=2048 if think else 512,
                 temperature=0.6 if think else 0.7)          # Qwen3 preporuka za oba moda
        msg = r.get("message", {})
        calls = [{"name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                 for c in msg.get("tool_calls") or []]
        out.append({"id": qid, "question": questions[qid]["question_en"], **measure(r),
                    "thinking_chars": len(msg.get("thinking") or ""),
                    "tool_calls": calls, "text": (msg.get("content") or "")[:300]})
    return out


# --- glavni tok ------------------------------------------------------------------

def section(title):
    print(f"\n=== {title} ===", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("MODEL", "qwen3:4b"))
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    m = args.model
    res = {"model": m, "date": str(date.today()), "quick": args.quick,
           "machine": {"cpu": platform.processor(), "logical_cpus": os.cpu_count(),
                       "ollama": ollama("/api/version")["version"]}}

    section("1. Ucitavanje modela (hladan start)")
    unload(m)
    r = measure(chat(m, [{"role": "user", "content": "Say OK."}], num_predict=4))
    res["load"] = {"load_s": r["load_s"], "memory_gb_ctx8192": loaded_memory_gb(m)}
    print(res["load"])

    section("2. Generisanje (200 tokena), num_ctx=8192")
    res["generation"] = [gen_test(m) for _ in range(2)]
    for x in res["generation"]:
        print(x)

    section("3. Prefill: pravi rezultati search_filing-a kao ulaz")
    sizes = [1000, 3000] if args.quick else [1000, 3000, 6000]
    res["prefill"] = [prefill_test(m, n) for n in sizes]
    for x in res["prefill"]:
        print(x)

    if not args.quick:
        section("4. num_ctx 16384: memorija i brzina")
        r = gen_test(m, num_ctx=16384)
        res["ctx16384"] = {**r, "memory_gb": loaded_memory_gb(m)}
        print(res["ctx16384"])
        chat(m, [{"role": "user", "content": "OK"}], num_predict=1)   # vrati model na 8192

        section("5a. Broj niti (num_thread) - generisanje")
        res["threads"] = {}
        for n in [2, 4, 8, 12]:
            res["threads"][n] = gen_test(m, extra_options={"num_thread": n})
            print(n, res["threads"][n])
        chat(m, [{"role": "user", "content": "OK"}], num_predict=1)   # vrati podrazumevane niti

        section("5b. Dva istovremena zahteva (kao 2 paralelna istrazivaca)")
        single = gen_test(m)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(2) as pool:
            both = list(pool.map(lambda _: gen_test(m), range(2)))
        res["concurrency"] = {"single_wall_s": single["wall_s"],
                              "two_parallel_wall_s": round(time.perf_counter() - t0, 1),
                              "two_sequential_estimate_s": round(2 * single["wall_s"], 1),
                              "parallel_runs": both}
        print({k: v for k, v in res["concurrency"].items() if k != "parallel_runs"})

    section("6. Pozivi nasih MCP alata (F1, C2, E3)")
    tools = asyncio.run(_mcp_tools())
    modes = [False] if args.quick else [False, True]
    res["tool_calls"] = {}
    for think in modes:
        key = "think_on" if think else "think_off"
        res["tool_calls"][key] = tool_call_test(m, tools, think)
        for x in res["tool_calls"][key]:
            print(key, x["id"], {k: x[k] for k in ("prompt_tokens", "output_tokens", "wall_s", "thinking_chars")})
            for c in x["tool_calls"]:
                print("    ->", c["name"], json.dumps(c["arguments"]))
            if not x["tool_calls"]:
                print("    (bez poziva alata) ", x["text"][:150].replace("\n", " "))

    out_dir = ROOT / "data" / "benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{res['date']}_{m.replace(':', '-')}{'_quick' if args.quick else ''}.json"
    path.write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    print(f"\nSacuvano: {path}")


if __name__ == "__main__":
    main()

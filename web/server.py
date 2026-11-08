"""Web backend: pokrece agente i salje njihove dogadjaje pregledacu UZIVO (SSE).

    pregledac --GET /api/run?question=..&mode=single|multi--> ovaj server --> run_agent / run_multi_agent
              <-------- tok dogadjaja (Server-Sent Events) ---------------    on_event

SSE (Server-Sent Events) = jednosmerni tok poruka od servera ka pregledacu preko obicnog HTTP-a.
Pregledac ga cita ugradjenim EventSource objektom; svaka poruka je jedan dogadjaj agenta kao JSON.
Agenti se NE menjaju: UI dobija iste dogadjaje (on_event) koje eval cuva kao trag.

Pokretanje (iz root foldera):  python -m web.server   ->  http://localhost:8000
"""
import asyncio
import json
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from mcp import Client, StdioServerParameters
from openai import AsyncOpenAI
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agents.multi_agent import run_multi_agent
from agents.single_agent import LLM_TIMEOUT_SECONDS, provider_options, run_agent
from mcp_server import search

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from metrics import PRICES, cost_usd  # noqa: E402  (cene iste kao u evalu)

MODES = ("single", "multi")
MAX_QUESTION_CHARS = 1000
CITATION = re.compile(r"([A-Z]{1,5})-10K-FY(\d{4})(?:#p(\d+))?")


async def run_events(question: str, mode: str, llm, mcp, model: str, extra_body: dict):
    """Dogadjaji jednog pokretanja, redom: run_start, sve sto agenti jave preko on_event, pa done/error.

    Agent radi u posebnom zadatku (task) i stavlja dogadjaje u red (queue); ovaj generator ih
    cita iz reda i predaje dalje cim stignu - zato pregledac vidi rad agenata uzivo."""
    queue: asyncio.Queue = asyncio.Queue()
    started = time.perf_counter()

    def emit(event_type: str, **data):
        queue.put_nowait({"type": event_type, "t": round(time.perf_counter() - started, 2), **data})

    async def work():
        try:
            if mode == "single":
                r = await run_agent(question, llm, mcp, model, extra_body=extra_body, on_event=emit)
                summary = {"llm_calls": r.steps, "tool_calls": len(r.tool_calls)}
            else:
                r = await run_multi_agent(question, llm, mcp, model, extra_body=extra_body, on_event=emit)
                summary = {"llm_calls": r.llm_calls, "tool_calls": r.tool_calls, "plan": r.plan,
                           "plan_fallback": r.plan_fallback, "research_seconds": r.research_seconds}
            emit("done", answer=r.answer, stop_reason=r.stop_reason, seconds=r.seconds,
                 input_tokens=r.input_tokens, output_tokens=r.output_tokens, max_input_tokens=r.max_input_tokens,
                 cost=cost_usd(r.input_tokens, r.output_tokens, model) if model in PRICES else None, **summary)
        except Exception as e:                       # greska API-ja itd. - pregledac dobija poruku, ne prazan ekran
            emit("error", error=repr(e))
        finally:
            queue.put_nowait(None)                   # znak da nema vise dogadjaja

    task = asyncio.create_task(work())
    try:
        yield {"type": "run_start", "t": 0.0, "mode": mode, "question": question, "model": model}
        while (item := await queue.get()) is not None:
            yield item
    finally:
        task.cancel()   # pregledac zatvorio vezu (ili kraj) -> prekini agenta, da ne trosi tokene uzalud


def passage(citation: str) -> dict:
    """Tekst citata: 'MU-10K-FY2023#p221' -> pasus iz 10-K; 'MU-10K-FY2023' -> podaci o izvestaju."""
    m = CITATION.fullmatch(citation.strip())
    if not m:
        return {"error": f"Neispravan citat: {citation}"}
    ticker, fiscal_year, index = m.group(1), int(m.group(2)), m.group(3)
    filing = search._filing_for(ticker, fiscal_year)
    if filing is None:
        return {"error": f"Nema 10-K za {ticker} FY{fiscal_year}"}
    info = {"citation": citation, "ticker": ticker, "fiscal_year": fiscal_year, "period_end": filing["period_end"],
            "filed": filing["filed"], "url": filing["url"]}
    if index is None:
        return {**info, "note": "Citat celog izveštaja: brojevi su iz XBRL podataka (get_financials)."}
    passages, _, _ = search._index(filing["key"])
    if int(index) >= len(passages):
        return {"error": f"Nema pasusa {citation}"}
    p = passages[int(index)]
    return {**info, "section": p.section, "text": p.text}


# --- HTTP rute ----------------------------------------------------------------------

async def api_config(request: Request):
    s = request.app.state
    return JSONResponse({"model": s.model, "provider": os.environ.get("OPENROUTER_PROVIDER")})


async def api_questions(request: Request):
    data = json.loads((ROOT / "eval" / "questions.json").read_text("utf-8"))
    return JSONResponse([{"id": q["id"], "type": q["type"], "set": q.get("set", "main"),
                          "question_en": q["question_en"], "question_sr": q["question"]} for q in data["questions"]])


async def api_passage(request: Request):
    result = passage(request.query_params.get("id", ""))
    return JSONResponse(result, status_code=404 if "error" in result else 200)


async def api_run(request: Request):
    question = (request.query_params.get("question") or "").strip()
    mode = request.query_params.get("mode", "multi")
    if not question or len(question) > MAX_QUESTION_CHARS or mode not in MODES:
        return JSONResponse({"error": f"Potrebno: question (do {MAX_QUESTION_CHARS} znakova) i mode {MODES}"},
                            status_code=400)
    s = request.app.state
    events = run_events(question, mode, s.llm, s.mcp, s.model, s.extra_body)
    return EventSourceResponse(
        ({"data": json.dumps(e, ensure_ascii=False, default=str)} async for e in events), ping=15)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Pri pokretanju: jedna MCP veza (podproces) i jedan klijent modela za sva pokretanja."""
    load_dotenv(ROOT / ".env")
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT))
    async with Client(params) as mcp:
        app.state.mcp = mcp
        app.state.llm = AsyncOpenAI(timeout=LLM_TIMEOUT_SECONDS)
        app.state.model = os.environ["MODEL"]
        app.state.extra_body = provider_options()
        yield


app = Starlette(
    routes=[Route("/api/config", api_config), Route("/api/questions", api_questions),
            Route("/api/passage", api_passage), Route("/api/run", api_run)],
    middleware=[Middleware(CORSMiddleware, allow_origins=[os.environ.get("UI_ORIGIN", "http://localhost:3000")],
                           allow_methods=["GET"])],
    lifespan=lifespan,
)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))

"use client";
// Jedno pokretanje agenta: otvori EventSource ka backendu i pretvaraj dogadjaje u stanje ekrana.
//
// reducer(stanje, dogadjaj) -> novo stanje. Ista ideja kao "trag" u evalu: ceo tok rada agenata
// je niz dogadjaja, a ekran je samo njihov pregled.

import { useEffect, useReducer } from "react";
import type { AgentEvent, DoneSummary, Lane, Mode } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type RunState = {
  status: "connecting" | "running" | "done" | "error";
  mode: Mode;
  elapsed: number;
  planner?: { status: "running" | "done"; seconds?: number; fallback?: boolean; errors: number };
  lanes: Lane[];
  synthesizer?: { status: "waiting" | "running" | "done"; seconds?: number; inputTokens?: number };
  done?: DoneSummary;
  error?: string;
  returnedIds: string[];  // svi ID-evi koje su alati vratili: citat van ovog skupa je nevazeci
};

const initial = (mode: Mode): RunState => ({
  status: "connecting",
  mode,
  elapsed: 0,
  planner: mode === "multi" ? { status: "running", errors: 0 } : undefined,
  lanes: mode === "single" ? [{ id: "agent", title: "Agent", status: "running", steps: [] }] : [],
  synthesizer: mode === "multi" ? { status: "waiting" } : undefined,
  returnedIds: [],
});

function laneId(e: { agent?: string }) {
  return e.agent ?? "agent";
}

function updateLane(state: RunState, id: string, change: (lane: Lane) => Lane): RunState {
  return { ...state, lanes: state.lanes.map((l) => (l.id === id ? change(l) : l)) };
}

export function reducer(state: RunState, e: AgentEvent): RunState {
  state = { ...state, elapsed: Math.max(state.elapsed, e.t) };
  switch (e.type) {
    case "run_start":
      return { ...state, status: "running" };

    case "plan":   // planer zavrsio: odmah prikazi kolonu za svaki podzadatak (i one koji cekaju red)
      return {
        ...state,
        planner: { ...state.planner!, status: "done", fallback: e.fallback },
        lanes: e.tasks.map((t) => ({
          id: `researcher:${t.id}`, title: `Istraživač ${t.id}`, task: t.task, status: "waiting", steps: [],
        })),
      };

    case "plan_error":
      return { ...state, planner: { ...state.planner!, errors: state.planner!.errors + 1 } };

    case "start":
      return updateLane(state, e.agent, (l) => ({ ...l, status: "running", task: e.task }));

    case "model":
      if (e.agent === "planner") return { ...state, planner: { ...state.planner!, seconds: e.seconds } };
      if (e.agent === "synthesizer") {
        return { ...state, synthesizer: { status: "done", seconds: e.seconds, inputTokens: e.input_tokens } };
      }
      return updateLane(state, laneId(e), (l) => ({
        ...l,
        steps: [...l.steps, { kind: "model", t: e.t, step: e.step, seconds: e.seconds,
                              input_tokens: e.input_tokens, output_tokens: e.output_tokens, finish: e.finish }],
      }));

    case "tool":
      return {
        ...updateLane(state, laneId(e), (l) => ({
          ...l,
          steps: [...l.steps, { kind: "tool", t: e.t, name: e.name, arguments: e.arguments, error: e.error,
                                returned_ids: e.returned_ids }],
        })),
        returnedIds: [...state.returnedIds, ...e.returned_ids],
      };

    case "finish": {   // istrazivac zavrsio; kad zavrse svi, radi sintetizator
      const next = updateLane(state, e.agent, (l) => ({
        ...l, status: e.stop_reason === "answer" ? "done" : "failed", answer: e.answer,
        stopReason: e.stop_reason, seconds: e.seconds,
      }));
      const allFinished = next.lanes.every((l) => l.status === "done" || l.status === "failed");
      return allFinished && next.synthesizer?.status === "waiting"
        ? { ...next, synthesizer: { status: "running" } }
        : next;
    }

    case "done": {
      const { type, t, ...summary } = e;
      const lanes = state.mode === "single"
        ? state.lanes.map((l) => ({ ...l, status: (e.stop_reason === "answer" ? "done" : "failed") as Lane["status"],
                                    stopReason: e.stop_reason }))
        : state.lanes;
      return { ...state, status: "done", done: summary, lanes, elapsed: e.seconds };
    }

    case "error":
      if (e.agent) return updateLane(state, e.agent, (l) => ({ ...l, status: "failed", stopReason: e.error }));
      return { ...state, status: "error", error: e.error };
  }
}

export function useRun(question: string, mode: Mode, runKey: number): RunState {
  const [state, dispatch] = useReducer(reducer, mode, initial);

  useEffect(() => {
    const url = `${API_URL}/api/run?mode=${mode}&question=${encodeURIComponent(question)}`;
    const source = new EventSource(url);
    let finished = false;

    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as AgentEvent;
      dispatch(event);
      if (event.type === "done" || (event.type === "error" && !event.agent)) {
        finished = true;
        source.close();   // VAZNO: EventSource se inace sam ponovo poveze, a to bi pokrenulo agenta ponovo
      }
    };
    source.onerror = () => {
      if (!finished) dispatch({ type: "error", t: 0, error: "Veza sa backend-om je prekinuta (radi li python -m web.server?)" });
      source.close();
    };
    return () => source.close();   // napustanje stranice -> backend prekida agenta
  }, [question, mode, runKey]);

  return state;
}

"use client";
// Jedno pokretanje uzivo: planer -> istrazivaci (paralelne kolone) -> sintetizator -> odgovor + brojke.

import { useEffect, useState } from "react";
import Answer from "./Answer";
import LaneCard from "./LaneCard";
import { useRun } from "@/lib/useRun";
import type { Mode } from "@/lib/types";

const TITLE: Record<Mode, string> = { single: "Jedan agent", multi: "Multi-agent" };

function subtasks(n: number) {   // srpska množina: 1 podzadatak, 2-4 podzadatka, 5+ podzadataka
  const last = n % 10, lastTwo = n % 100;
  if (last === 1 && lastTwo !== 11) return `${n} podzadatak`;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${n} podzadatka`;
  return `${n} podzadataka`;
}

function useClock(running: boolean) {
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(started);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [running]);
  return (now - started) / 1000;
}

type Props = { question: string; mode: Mode; runKey: number; onCite: (id: string) => void };

export default function RunView({ question, mode, runKey, onCite }: Props) {
  const run = useRun(question, mode, runKey);
  const running = run.status === "connecting" || run.status === "running";
  const clock = useClock(running);
  const seconds = run.done ? run.done.seconds : clock;

  return (
    <div className="run">
      <header className="run-head">
        <h2>{TITLE[mode]}</h2>
        <span className={`badge badge-${running ? "running" : run.status === "done" ? "done" : "failed"}`}>
          {running && <span className="spinner" aria-hidden />}
          {running ? "radi" : run.status === "done" ? "gotovo" : "greška"} · {seconds.toFixed(1)} s
        </span>
      </header>

      {run.planner && (
        <section className="card planner">
          <header className="card-head">
            <strong>Planer</strong>
            <span className={`badge badge-${run.planner.status === "done" ? "done" : "running"}`}>
              {run.planner.status === "running" && <span className="spinner" aria-hidden />}
              {run.planner.status === "done"
                ? `${subtasks(run.lanes.length)}${run.planner.seconds ? ` · ${run.planner.seconds}s` : ""}`
                : "pravi plan"}
            </span>
          </header>
          {run.planner.errors > 0 && <p className="bad">Neispravan plan, ponovni pokušaj ({run.planner.errors})</p>}
          {run.planner.fallback && <p className="bad">Planer nije uspeo: ceo zadatak ide jednom istraživaču</p>}
        </section>
      )}

      {run.lanes.length > 0 && (
        <div className={`lanes ${mode === "multi" ? "lanes-multi" : ""}`}>
          {run.lanes.map((lane) => (
            <LaneCard key={lane.id} lane={lane} returnedIds={run.returnedIds} onCite={onCite} showFinding={mode === "multi"} />
          ))}
        </div>
      )}

      {run.synthesizer && (
        <section className="card synth">
          <header className="card-head">
            <strong>Sintetizator</strong>
            <span className={`badge badge-${run.synthesizer.status === "done" ? "done" : run.synthesizer.status}`}>
              {run.synthesizer.status === "running" && <span className="spinner" aria-hidden />}
              {run.synthesizer.status === "waiting" ? "čeka nalaze" : run.synthesizer.status === "running"
                ? "piše odgovor" : `gotovo · ${run.synthesizer.seconds}s`}
            </span>
          </header>
        </section>
      )}

      {run.error && <p className="bad card">{run.error}</p>}

      {run.done && (
        <>
          <section className="card answer">
            <header className="card-head">
              <strong>Odgovor</strong>
              {run.done.stop_reason !== "answer" && <span className="badge badge-failed">{run.done.stop_reason}</span>}
            </header>
            {run.done.answer
              ? <Answer text={run.done.answer} returnedIds={run.returnedIds} onCite={onCite} />
              : <p className="bad">Nema odgovora ({run.done.stop_reason}).</p>}
          </section>
          <dl className="metrics">
            <div><dt>vreme</dt><dd>{run.done.seconds} s</dd></div>
            <div><dt>pozivi modela</dt><dd>{run.done.llm_calls}</dd></div>
            <div><dt>pozivi alata</dt><dd>{run.done.tool_calls}</dd></div>
            <div><dt>tokeni ulaz / izlaz</dt>
              <dd>{run.done.input_tokens.toLocaleString("sr-RS")} / {run.done.output_tokens.toLocaleString("sr-RS")}</dd></div>
            <div><dt>najveći kontekst</dt><dd>{run.done.max_input_tokens.toLocaleString("sr-RS")}</dd></div>
            <div><dt>cena</dt><dd>{run.done.cost === null ? "-" : `$${run.done.cost.toFixed(5)}`}</dd></div>
          </dl>
        </>
      )}
    </div>
  );
}

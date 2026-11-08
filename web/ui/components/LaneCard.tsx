"use client";
// Jedna kolona: jedan agent ili jedan istrazivac. Svaki korak petlje je red:
// poziv modela (tokeni, sekunde) ili poziv alata (ime, argumenti, vraceni izvori).

import Answer from "./Answer";
import type { Lane, Step } from "@/lib/types";

const STATUS: Record<Lane["status"], string> = {
  waiting: "čeka red", running: "radi", done: "gotovo", failed: "bez odgovora",
};

function formatArgs(raw: string): string {
  try {
    const args = JSON.parse(raw) as Record<string, unknown>;
    return Object.entries(args)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
      .join(" · ");
  } catch {
    return raw;   // neispravan JSON od modela - prikazi kako je stigao
  }
}

function StepRow({ step, onCite }: { step: Step; onCite: (id: string) => void }) {
  if (step.kind === "model") {
    return (
      <li className="step step-model">
        <span className="t">{step.t.toFixed(1)}s</span>
        <span className="label">model{step.step ? ` #${step.step}` : ""}</span>
        <span className="muted">
          {step.input_tokens.toLocaleString("sr-RS")} → {step.output_tokens.toLocaleString("sr-RS")} tok · {step.seconds}s
          {step.finish === "tool_calls" ? " · traži alat" : step.finish === "stop" ? " · odgovor" : ` · ${step.finish}`}
        </span>
      </li>
    );
  }
  return (
    <li className={`step step-tool ${step.error ? "step-error" : ""}`}>
      <span className="t">{step.t.toFixed(1)}s</span>
      <span className="label tool-name">{step.name}</span>
      <span className="args">{formatArgs(step.arguments)}</span>
      {step.error && <span className="bad">greška - model dobija poruku i ispravlja se</span>}
      {step.returned_ids.length > 0 && (
        <span className="ids">
          {step.returned_ids.slice(0, 6).map((id) => (
            <button key={id} type="button" className="cite cite-ok" onClick={() => onCite(id)}>{id}</button>
          ))}
          {step.returned_ids.length > 6 && <span className="muted">+{step.returned_ids.length - 6}</span>}
        </span>
      )}
    </li>
  );
}

type Props = { lane: Lane; returnedIds: string[]; onCite: (id: string) => void; showFinding: boolean };

export default function LaneCard({ lane, returnedIds, onCite, showFinding }: Props) {
  return (
    <section className={`card lane lane-${lane.status}`}>
      <header className="card-head">
        <strong>{lane.title}</strong>
        <span className={`badge badge-${lane.status}`}>
          {lane.status === "running" && <span className="spinner" aria-hidden />}
          {STATUS[lane.status]}
          {lane.seconds !== undefined && ` · ${lane.seconds}s`}
        </span>
      </header>
      {lane.task && <p className="task">{lane.task}</p>}
      <ol className="steps">
        {lane.steps.map((s, i) => <StepRow key={i} step={s} onCite={onCite} />)}
      </ol>
      {lane.status === "failed" && lane.stopReason && <p className="bad">Stao: {lane.stopReason}</p>}
      {showFinding && lane.answer && (
        <details className="finding">
          <summary>Nalaz istraživača</summary>
          <Answer text={lane.answer} returnedIds={returnedIds} onCite={onCite} />
        </details>
      )}
    </section>
  );
}

"use client";
// Pocetna strana: pitanje + rezim (jedan agent / multi-agent / oba uporedo), pa tok rada uzivo.

import { useEffect, useState } from "react";
import PassageModal from "@/components/PassageModal";
import RunView from "@/components/RunView";
import { API_URL } from "@/lib/useRun";
import type { Mode, Question } from "@/lib/types";

type Choice = Mode | "both";
const CHOICES: { value: Choice; label: string }[] = [
  { value: "single", label: "Jedan agent" },
  { value: "multi", label: "Multi-agent" },
  { value: "both", label: "Uporedo" },
];

export default function Home() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [config, setConfig] = useState<{ model: string; provider: string | null } | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [question, setQuestion] = useState("");
  const [choice, setChoice] = useState<Choice>("both");
  const [submitted, setSubmitted] = useState<{ question: string; choice: Choice; key: number } | null>(null);
  const [citation, setCitation] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetch(`${API_URL}/api/questions`), fetch(`${API_URL}/api/config`)])
      .then(async ([q, c]) => {
        setQuestions(await q.json());
        setConfig(await c.json());
      })
      .catch(() => setBackendDown(true));
  }, []);

  function run() {
    const q = question.trim();
    if (q) setSubmitted({ question: q, choice, key: Date.now() });
  }

  const modes: Mode[] = submitted ? (submitted.choice === "both" ? ["single", "multi"] : [submitted.choice]) : [];

  return (
    <main>
      <header className="page-head">
        <div>
          <h1>Multi-agent istraživač</h1>
          <p className="muted">
            SEC EDGAR · 18 kompanija · 10-K izveštaji preko MCP servera
            {config && <> · model <code>{config.model}</code>{config.provider && <> ({config.provider})</>}</>}
          </p>
        </div>
      </header>

      {backendDown && (
        <p className="card bad">Backend nije dostupan na {API_URL}. Pokreni: <code>python -m web.server</code></p>
      )}

      <section className="card controls">
        <label htmlFor="question">Pitanje (na engleskom)</label>
        <textarea
          id="question"
          rows={2}
          value={question}
          placeholder="npr. Why did Micron report a loss in FY2023, according to its 10-K?"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); }}
        />
        <div className="row">
          <select
            aria-label="Pitanje iz evala"
            value=""
            onChange={(e) => {
              const q = questions.find((x) => x.id === e.target.value);
              if (q) setQuestion(q.question_en);
            }}
          >
            <option value="">Pitanje iz evala…</option>
            {questions.map((q) => (
              <option key={q.id} value={q.id}>{q.id} · {q.question_sr}</option>
            ))}
          </select>
          <div className="segmented" role="radiogroup" aria-label="Režim">
            {CHOICES.map((c) => (
              <button key={c.value} type="button" role="radio" aria-checked={choice === c.value}
                      className={choice === c.value ? "active" : ""} onClick={() => setChoice(c.value)}>
                {c.label}
              </button>
            ))}
          </div>
          <button type="button" className="primary" onClick={run} disabled={!question.trim() || backendDown}>
            Pokreni
          </button>
        </div>
      </section>

      {submitted && (
        <div className={`runs ${modes.length > 1 ? "runs-two" : ""}`}>
          {modes.map((m) => (
            <RunView key={`${m}-${submitted.key}`} question={submitted.question} mode={m} runKey={submitted.key}
                     onCite={setCitation} />
          ))}
        </div>
      )}

      {citation && <PassageModal id={citation} onClose={() => setCitation(null)} />}
    </main>
  );
}

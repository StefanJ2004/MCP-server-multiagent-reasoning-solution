"use client";
// Klik na citat -> tacan tekst iz 10-K izvestaja (GET /api/passage), da se citat proveri na licu mesta.

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/useRun";

type Passage = {
  citation: string; ticker: string; fiscal_year: number; period_end: string; filed: string; url: string;
  section?: string; text?: string; note?: string; error?: string;
};

export default function PassageModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData] = useState<Passage | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/passage?id=${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ error: "Backend nije dostupan" } as Passage));
  }, [id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Citat ${id}`}>
        <div className="modal-head">
          <code>{id}</code>
          <button type="button" className="ghost" onClick={onClose} aria-label="Zatvori">✕</button>
        </div>
        {!data && <p className="muted">Učitavam…</p>}
        {data?.error && <p className="bad">{data.error}</p>}
        {data && !data.error && (
          <>
            <p className="muted">
              {data.ticker} · 10-K za fiskalnu godinu koja se završava {data.period_end} · podnet {data.filed} ·{" "}
              <a href={data.url} target="_blank" rel="noreferrer">SEC EDGAR ↗</a>
            </p>
            {data.section && <h4>{data.section}</h4>}
            {data.text && <blockquote>{data.text}</blockquote>}
            {data.note && <p>{data.note}</p>}
          </>
        )}
      </div>
    </div>
  );
}

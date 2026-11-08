"use client";
// Odgovor kao markdown (tabele, liste), sa citatima kao dugmicima.
// Zeleno = taj ID je zaista vratio neki alat u ovom pokretanju; crveno = nije (isto pravilo kao u evalu).

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { citationFromHref, linkCitations } from "@/lib/citations";

type Props = { text: string; returnedIds: string[]; onCite: (id: string) => void };

export default function Answer({ text, returnedIds, onCite }: Props) {
  const returned = new Set(returnedIds);
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const id = citationFromHref(href);
            if (!id) return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
            const valid = returned.has(id);
            return (
              <button
                type="button"
                className={`cite ${valid ? "cite-ok" : "cite-bad"}`}
                title={valid ? "Izvor je vratio alat u ovom pokretanju" : "Ovaj ID nije vratio nijedan alat u ovom pokretanju"}
                onClick={() => onCite(id)}
              >
                {children}
              </button>
            );
          },
        }}
      >
        {linkCitations(text)}
      </ReactMarkdown>
    </div>
  );
}

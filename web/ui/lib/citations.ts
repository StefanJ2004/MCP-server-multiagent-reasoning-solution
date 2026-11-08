// Citati u odgovoru -> markdown linkovi "#cite=<ID>", koje Answer prikazuje kao dugmice.
// Ista pravila kao eval/metrics.py: [MU-10K-FY2023#p223, #p227] se razvija u dva puna ID-a.

const CITATION_ID = /^[A-Z]{1,5}-10K-FY\d{4}(#p\d+)?$/;

export function linkCitations(text: string): string {
  // [..] koji NIJE vec markdown link ([tekst](url))
  return text.replace(/\[([^\[\]]+)\](?!\()/g, (whole, inner: string) => {
    let lastSource: string | null = null;
    let found = false;
    const parts = inner.split(/[,;]/).map((part) => {
      const p = part.trim();
      let id: string | null = null;
      if (CITATION_ID.test(p)) {
        id = p;
        lastSource = p.split("#")[0];
      } else if (/^#p\d+$/.test(p) && lastSource) {
        id = lastSource + p;
      }
      if (!id) return p;
      found = true;
      return `[${p}](#cite=${encodeURIComponent(id)})`;
    });
    return found ? parts.join(" ") : whole;
  });
}

export function citationFromHref(href: string | undefined): string | null {
  return href?.startsWith("#cite=") ? decodeURIComponent(href.slice("#cite=".length)) : null;
}

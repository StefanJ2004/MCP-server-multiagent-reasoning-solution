"""Automatske metrike evala: provera citata, cena, statistika. Ciste funkcije, bez modela (testirane)."""
import re
import statistics

from mcp_server.companies import COMPANIES

# USD po milionu tokena (ulaz, izlaz) za zakucanog provajdera na OpenRouter-u, cene od 2026-11-08.
# Kesirani ulaz je jeftiniji, pa je cena izracunata ovako GORNJA granica.
PRICES = {
    "deepseek/deepseek-v4.1-flash": (0.075, 0.30),   # Alibaba Cloud
    "google/gemma-4-26b-a4b-it": (0.07, 0.34),       # DeepInfra (fp8); Google Vertex spaja paralelne pozive alata
}

_CITATION = re.compile(r"[A-Z]{1,5}-10K-FY\d{4}(?:#p\d+)?")
_BRACKET = re.compile(r"\[([^\[\]]+)\]")


def _looks_like_citation(part: str) -> bool:
    """Pokusaj citata koji nije u ispravnom formatu, npr. [INTC], [Intel 10-K] ili [t1]
    (ID podzadatka multi-agenta - interni, korisniku ne znaci nista)."""
    return (part.upper() in COMPANIES or "10K" in part.upper() or "10-K" in part.upper()
            or re.fullmatch(r"t\d+", part) is not None)


def extract_citations(answer: str | None) -> list[str]:
    """Svi citati iz odgovora. Skraceni oblik [MU-10K-FY2023#p223, #p227] se razvija u pune ID-eve.
    Neispravni pokusaji (npr. [INTC]) se vracaju takvi kakvi jesu, pa kasnije ispadaju nevazeci."""
    found = []
    for content in _BRACKET.findall(answer or ""):
        last_source = None
        for part in re.split(r"[,;]", content):
            part = part.strip()
            if _CITATION.fullmatch(part):
                last_source = part.split("#")[0]
                found.append(part)
            elif re.fullmatch(r"#p\d+", part) and last_source:
                found.append(last_source + part)
            elif part and _looks_like_citation(part):
                found.append(part)
    return found


def check_citations(answer: str | None, returned: set[str]) -> dict:
    """Citat je vazeci samo ako je taj ID zaista vratio neki alat u ISTOM pokretanju."""
    citations = extract_citations(answer)
    invalid = [c for c in citations if c not in returned]
    return {"citations": len(citations), "valid": len(citations) - len(invalid), "invalid": invalid}


def cost_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    price_in, price_out = PRICES[model]          # KeyError = dodaj cenu novog modela u PRICES
    return input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out


def summary(values: list[float]) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"mean": None, "median": None, "max": None}
    return {"mean": statistics.mean(values), "median": statistics.median(values), "max": max(values)}


def stability(scores_by_question: dict[str, list[float]]) -> float | None:
    """Udeo pitanja na kojima su SVA pokretanja dobila istu ocenu."""
    multi_run = [s for s in scores_by_question.values() if len(s) > 1]
    if not multi_run:
        return None
    return sum(len(set(s)) == 1 for s in multi_run) / len(multi_run)

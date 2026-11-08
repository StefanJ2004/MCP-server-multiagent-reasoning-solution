# Eval izveštaj: 2026-11-08_1949

Model: `google/gemma-4-26b-a4b-it`, provajder(i): DeepInfra; modeli u odgovorima: google/gemma-4-26b-a4b-it; pokretanja: 3.

Ocenjivanje: Claude, naslepo (to_grade.json bez oznake sistema), po pravilima iz questions.json; 1 / 0,5 / 0.
Cena je gornja granica (cena zakucanog provajdera iz eval/metrics.py, bez popusta za keširan ulaz).

## Po sistemu

| Metrika | Jedan agent | Multi-agent |
|---|---|---|
| odgovora | 48 | 48 |
| tačnost: main (12) | 95.8% | 91.7% |
| tačnost: extra (B1, H1–H3) | 70.8% | 91.7% |
| tačnost: sve | 89.6% | 91.7% |
| brojevi tačni | 92.9% | 95.6% |
| stabilnost (ista ocena u svim pokretanjima) | 93.8% | 87.5% |
| cena po tačnom odgovoru ($) | 0.00076 | 0.00124 |
| vreme: prosek / medijana / max (s) | 6.5 / 7.0 / 14.2 | 11.1 / 11.2 / 23.7 |
| ulazni tokeni (prosek) | 8,142 | 12,135 |
| izlazni tokeni (prosek) | 317 | 852 |
| najveći kontekst u 1 pozivu: prosek / max | 2,414 / 7,841 | 1,930 / 4,496 |
| cena po pitanju (prosek, $) | 0.00068 | 0.00114 |
| cena ukupno ($) | 0.0325 | 0.0547 |
| pozivi modela (prosek) | 3.6 | 9.1 |
| pozivi alata (prosek): ukupno / financials / search | 3.5 / 2.3 / 0.9 | 4.2 / 2.8 / 1.4 |
| greške alata (ukupno, model se ispravlja) | 3 | 0 |
| citati: važeći / ukupno | 203 / 204 (99.5%) | 221 / 224 (98.7%) |
| odgovori sa bar jednim nevažećim citatom | 1 | 3 |
| odgovori bez ijednog citata | 3 | 1 |
| razlozi zaustavljanja | answer: 45, max_steps: 3 | answer: 48 |
| rezervni plan (planer nije uspeo) | - | 0 |
| podzadataka po pitanju (prosek) | - | 2.9 |
| ubrzanje od paralelizma (zbir vremena istraživača / trajanje faze) | - | 1.92× |

## Po pitanju

| Pitanje | Tip | single: ocene | multi: ocene | single: tokena (ulaz) | multi: tokena (ulaz) |
|---|---|---|---|---|---|
| F1 | factual | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,223 | 3,501 |
| F2 | factual | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,231 | 3,559 |
| F3 | factual | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,234 | 3,525 |
| C1 | comparative | 0.5 0.5 0.5 | 0.5 0.5 0.5 | 2,957 | 9,676 |
| C2 | comparative | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,554 | 8,457 |
| C3 | comparative | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 8,839 | 8,914 |
| C4 | comparative | 1.0 1.0 1.0 | 1.0 0.5 0.0 | 2,734 | 18,908 |
| E1 | explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 4,238 | 6,435 |
| E2 | explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 4,273 | 4,484 |
| E3 | explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 5,752 | 4,653 |
| U1 | unanswerable | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 1,036 | 3,560 |
| U2 | unanswerable | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,230 | 3,701 |
| B1 | breadth | 0.0 0.0 0.0 | 1.0 1.0 1.0 | 29,273 | 45,705 |
| H1 | hard_multi_explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 11,385 | 16,043 |
| H2 | hard_multi_hop | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 12,035 | 34,099 |
| H3 | hard_fy_trap | 1.0 0.5 1.0 | 0.5 0.5 1.0 | 36,285 | 18,939 |

## Nevažeći citati

- multi run 1 U1: t1
- multi run 2 C4: t2
- multi run 3 U1: t1
- single run 3 H3: BBY-10K-FY2025 (via get_financials)

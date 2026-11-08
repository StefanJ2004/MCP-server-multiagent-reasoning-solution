# Eval izveštaj: 2026-11-08_1903

Model: `deepseek/deepseek-v4.1-flash`, provajder(i): Alibaba; modeli u odgovorima: deepseek/deepseek-v4.1-flash; pokretanja: 3.

Ocenjivanje: Claude, naslepo (to_grade.json bez oznake sistema), po pravilima iz questions.json; 1 / 0,5 / 0.
Cena je gornja granica (cena zakucanog provajdera iz eval/metrics.py, bez popusta za keširan ulaz).

## Po sistemu

| Metrika | Jedan agent | Multi-agent |
|---|---|---|
| odgovora | 48 | 48 |
| tačnost: main (12) | 100.0% | 100.0% |
| tačnost: extra (B1, H1–H3) | 91.7% | 91.7% |
| tačnost: sve | 97.9% | 97.9% |
| brojevi tačni | 100.0% | 95.6% |
| stabilnost (ista ocena u svim pokretanjima) | 87.5% | 93.8% |
| cena po tačnom odgovoru ($) | 0.00071 | 0.00203 |
| vreme: prosek / medijana / max (s) | 5.8 / 5.2 / 12.4 | 11.1 / 12.6 / 21.9 |
| ulazni tokeni (prosek) | 6,495 | 18,759 |
| izlazni tokeni (prosek) | 706 | 1,950 |
| najveći kontekst u 1 pozivu: prosek / max | 3,021 / 6,862 | 3,496 / 9,456 |
| cena po pitanju (prosek, $) | 0.00070 | 0.00199 |
| cena ukupno ($) | 0.0336 | 0.0956 |
| pozivi modela (prosek) | 2.8 | 9.2 |
| pozivi alata (prosek): ukupno / financials / search | 4.3 / 2.9 / 0.9 | 6.2 / 3.1 / 3.1 |
| greške alata (ukupno, model se ispravlja) | 0 | 0 |
| citati: važeći / ukupno | 384 / 386 (99.5%) | 347 / 356 (97.5%) |
| odgovori sa bar jednim nevažećim citatom | 2 | 3 |
| odgovori bez ijednog citata | 1 | 0 |
| razlozi zaustavljanja | answer: 48 | answer: 48 |
| rezervni plan (planer nije uspeo) | - | 0 |
| podzadataka po pitanju (prosek) | - | 2.9 |
| ubrzanje od paralelizma (zbir vremena istraživača / trajanje faze) | - | 1.98× |

## Po pitanju

| Pitanje | Tip | single: ocene | multi: ocene | single: tokena (ulaz) | multi: tokena (ulaz) |
|---|---|---|---|---|---|
| F1 | factual | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,852 | 4,062 |
| F2 | factual | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 2,891 | 4,382 |
| F3 | factual | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 4,863 | 4,133 |
| C1 | comparative | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 4,511 | 11,487 |
| C2 | comparative | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 3,333 | 10,805 |
| C3 | comparative | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 3,345 | 10,834 |
| C4 | comparative | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 5,450 | 13,469 |
| E1 | explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 3,963 | 12,009 |
| E2 | explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 3,758 | 10,709 |
| E3 | explanatory | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 3,982 | 14,688 |
| U1 | unanswerable | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 5,537 | 4,245 |
| U2 | unanswerable | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 4,013 | 21,595 |
| B1 | breadth | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 9,811 | 60,659 |
| H1 | hard_multi_explanatory | 1.0 0.5 1.0 | 1.0 1.0 1.0 | 19,011 | 24,606 |
| H2 | hard_multi_hop | 1.0 1.0 1.0 | 1.0 1.0 1.0 | 10,373 | 42,936 |
| H3 | hard_fy_trap | 0.5 1.0 1.0 | 0.5 1.0 0.5 | 16,234 | 49,532 |

## Nevažeći citati

- multi run 1 U1: t1, t1, t1
- multi run 2 U1: t1, t1, t1
- single run 2 H2: per each company's 10-K
- multi run 3 U1: t1, t1, t1
- single run 3 H2: each company's 10-K FY2024

# Timski projekat: Multi-agent istraživač + MCP server

## Kontekst

- Tim: 4 programera (studenti softverskog inženjerstva), troje ima Claude Pro.
- Cilj: portfolio/CV projekat koji pokazuje rad sa AI agentima, MCP-om i evaluacijom.
- Budžet: ~30 sati ukupnog rada uz Claude Code.
- Način rada: **radimo zajedno (mob programming), ne delimo posao po osobama** — glavni cilj je da svi naučimo sve delove sistema.

## Šta pravimo

Kombinacija dva sistema:

1. **MCP server** koji izlaže naše podatke i alate (3–5 alata nad izabranim domenom).
2. **Multi-agent istraživač** nad tim serverom:
   - **Planer** razbija korisničko pitanje na podzadatke.
   - **Istraživači** (paralelno) rešavaju podzadatke koristeći MCP alate i web pretragu.
   - **Sintetizator** spaja rezultate u izveštaj sa citatima/izvorima.
3. **UI** koji u realnom vremenu prikazuje tok agenata (ko radi šta, koji alat zove, šta je vraćeno).
4. **Evaluacija**: skup od 10+ pitanja, poređenje multi-agent sistema sa jednim agentom (tačnost, kvalitet citata).

```
Korisnik → UI (Next.js) → Orkestrator
                            ├─ Planer
                            ├─ Istraživači (paralelno): MCP alati + web pretraga
                            └─ Sintetizator: izveštaj sa citatima
                                     ↓
                        MCP server: naši podaci i alati
```

## Otvorene odluke (rešiti u fazi 0)

- **Domen podataka** — kandidati:
  - Agri parcele i usevi (Vojvodina) — povezuje se sa idejom za hakaton.
  - Javni podaci Srbije (data.gov.rs).
  - Nešto naše (npr. FON rasporedi, predmeti, ispitni rokovi).
- **Jezik MCP servera**: Python ili TypeScript.
- **Model/SDK** za agente.

## Plan (~30 h)

| Faza | Sati | Zadatak | Šta učimo |
|---|---|---|---|
| 0. Dizajn | 2 | Izbor domena i podataka; 10 pitanja koja sistem mora da reši (postaje eval set) | Definisanje problema |
| 1. MCP server | 6 | 3–5 alata nad podacima; testiranje iz Claude Desktopa | MCP protokol, dizajn alata |
| 2. Jedan agent | 5 | Agent petlja ručno: model → poziv alata → rezultat → ponovo | Kako agenti rade |
| 3. Multi-agent | 7 | Planer, paralelni istraživači, sintetizator, deljeno stanje | Orkestracija, paralelizam |
| 4. Evaluacija | 4 | Pokretanje eval seta, ocena tačnosti i citata, poređenje sa jednim agentom | Eval, metrike |
| 5. UI i trace | 4 | Prikaz toka agenata u realnom vremenu | Streaming, observability |
| 6. Demo | 2 | README, dijagram arhitekture, video od 2 min, objava na GitHub-u | Prezentacija |

Evaluacija je najvažniji deo za CV: konkretan rezultat tipa „multi-agent tačan u 8/10 naspram 5/10 za jednog agenta“.

## Pravila rada tima

- **Rotacija vozača na 45–60 min**; rotira se i čiji se Pro nalog koristi.
- **„Objasni pre prihvatanja“**: nijedna izmena ne ulazi u kod dok neko ne objasni ostalima šta radi.
- **Claude Code piše kod, tim uči iz objašnjenja** (izmenjeno 2026-11-07, ranije: „ključne koncepte pišemo ručno"). I dalje bez frameworka za agent petlju i MCP alate, da bi se mehanika videla u kodu.
- **Teach-back** na kraju svake faze: neko ko nije vozio objašnjava šta je napravljeno.

## Uputstva za Claude Code

- Komuniciraj na srpskom, direktno i tehnički precizno.
- Ovo je projekat za učenje, ali kod pišeš ti: piši kompletan kod, a uz ključne delove (**agent petlja, orkestracija, MCP alati**) objasni kako rade i zašto su tako napravljeni, da tim može da ih objasni na teach-back-u.
- Kod treba da bude čitljiv za učenje: jasna imena, kratki komentari na srpskom gde logika nije očigledna.
- Pre većih izmena kratko opiši plan i čekaj potvrdu.
- Vodi računa o fazama iz plana; kad je faza gotova, predloži šta proveriti pre prelaska na sledeću.
- Ažuriraj odeljak „Status“ ispod kad tim završi fazu ili donese odluku.

## Status

- [x] Faza 0 — završena 2026-11-07 (teach-back urađen)
  - [x] Domen: SEC EDGAR (XBRL companyfacts API + tekst 10-K izveštaja)
  - [x] Kompanije (18, sve imaju prihod, bruto/operativni/neto profit za FY2022+; čipovi i softver i R&D):
    - Čipovi: NVDA, AMD, INTC, AVGO, TXN, MU, AMAT, ADI, LRCX
    - Softver: MSFT, CRM, ADBE, NOW, CSCO
    - Maloprodaja: HD, LOW, BBY, DG
  - [x] Vrednosti provereni (MSFT, AMD, HD, NVDA): poklapaju se sa objavljenim izveštajima, bez konflikata među prijavama za FY2022+
  - Zamke u podacima (rešava MCP server, ne model): duplikati istog perioda kroz više 10-K prijava; `fy` = godina prijave, ne perioda; fiskalna ≠ kalendarska godina; ista metrika pod više XBRL tagova (potrebna mapa tagova)
  - [x] Jezik: Python
  - [x] Model/SDK: Qwen3 4B lokalno preko Ollama (samo CPU), `openai` Python SDK na Ollama OpenAI-kompatibilnom endpointu (`http://localhost:11434/v1`); `mcp` SDK za server i klijent
  - [x] Konvencija: FY = kalendarska godina u kojoj se fiskalna godina završava (polje `fy` iz EDGAR-a je nepouzdano)
  - [x] Eval set: 12 pitanja u `eval/questions.json` (3 činjenična, 4 uporedna, 3 sa objašnjenjem, 2 bez odgovora); svi odgovori provereni (brojevi iz XBRL, objašnjenja E1–E3 iz teksta 10-K MD&A)
  - [x] Jezik evala: engleski (`question_en`); srpski za UI/demo
- [ ] Faza 1 — u toku
  - [x] Skelet projekta (pyproject, .venv, struktura foldera, `scripts/download_data.py`, git init)
  - [x] Dizajn MCP alata: 3 alata
    - `list_companies(sector?)` — tikeri, imena, sektori, kraj fiskalne godine
    - `get_financials(ticker, metrics, fiscal_years)` — čisti brojevi (dedup, mapa tagova, FY konvencija) + izvedene metrike (marže, rnd_pct, rast) koje računa server; milijarde USD sa decimalama; uz svaki broj period i `source_id`
    - `search_filing(ticker, fiscal_year, query)` — 2–3 isečka iz 10-K, BM25 pisan ručno
    - Bez `compare_companies`: poređenje rade agenti, da alat ne bi „pojeo" prednost multi-agenta na uporednim pitanjima
  - [x] `mcp_server/financials.py` + `tests/test_financials.py` (30 testova, prolaze)
  - [x] `mcp_server/search.py` (BM25 ručno, prozori 150 reči sa preklapanjem, Risk Factors ×0,5) + `tests/test_search.py` (ukupno 49 testova, prolaze)
  - Pouka: BM25 je dobar za konkretne finansijske termine („valuation allowance", „inventory write-down"), a loš za neodređena pitanja („reasons for loss") → opis alata i prompt istraživača moraju tražiti konkretne termine i više pretraga
  - [x] `mcp_server/server.py` (MCP SDK 2.x: `MCPServer`, ne `FastMCP`; kompaktan JSON; enum metrika u šemi) + `tests/test_server.py` (ukupno 55 testova, prolaze, uključujući stdio podproces)
  - [ ] Ručni test: MCP Inspector i Claude Desktop (uputstvo u README)
- Handoff na drugi računar (2026-11-08): vidi `handoff.md`
- [ ] Faza 2
- [ ] Faza 3
- [ ] Faza 4
- [ ] Faza 5
- [ ] Faza 6

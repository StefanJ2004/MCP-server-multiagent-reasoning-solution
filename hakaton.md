# Timski projekat: Multi-agent istraživač + MCP server

## Kontekst

- Tim: 4 programera (studenti softverskog inženjerstva), troje ima Claude Pro.
- Cilj: portfolio/CV projekat koji pokazuje rad sa AI agentima, MCP-om i evaluacijom.
- **Glavni cilj (potvrđeno 2026-11-08): pravimo sistem sa što više agenata, a evalom merimo da li zaista daje bolje rezultate od jednog agenta.**
- Budžet: ~30 sati ukupnog rada uz Claude Code.
- Model: DeepSeek V4.1 Flash preko plaćenog API-ja (odluka tima 2026-11-08, umesto lokalne Ollame).
- Način rada: **radimo zajedno (mob programming), ne delimo posao po osobama** — glavni cilj je da svi naučimo sve delove sistema.

## Šta pravimo

Kombinacija dva sistema:

1. **MCP server** koji izlaže naše podatke i alate (3–5 alata nad izabranim domenom).
2. **Multi-agent istraživač** nad tim serverom:
   - **Planer** razbija korisničko pitanje na podzadatke.
   - **Istraživači** (paralelno) rešavaju podzadatke koristeći MCP alate. Broj agenata ograničavaju cena i limit API-ja (2500 istovremenih zahteva), a ne lokalni hardver.
   - **Sintetizator** spaja rezultate u izveštaj sa citatima/izvorima.
3. **UI** koji u realnom vremenu prikazuje tok agenata (ko radi šta, koji alat zove, šta je vraćeno).
4. **Evaluacija**: 12 pitanja + posebno označeno 13. pitanje sa svih 18 kompanija; poređenje multi-agent sistema sa jednim agentom (tačnost, kvalitet citata).

```
Korisnik → UI (Next.js) → Orkestrator
                            ├─ Planer
                            ├─ Istraživači (paralelno): MCP alati
                            └─ Sintetizator: izveštaj sa citatima
                                     ↓
                        MCP server: naši podaci i alati

Pozivi modelu: orkestrator → DeepSeek API (paralelno, `asyncio`).
MCP server i podaci su lokalni, na računaru sa orkestratorom.
```

## Plan (~30 h, zaključan 2026-11-08, model promenjen istog dana)

| Faza | Sati | Zadatak | Šta učimo |
|---|---|---|---|
| 0. Dizajn | 2 | Izbor domena i podataka; 10 pitanja koja sistem mora da reši (postaje eval set) | Definisanje problema |
| 1. MCP server | 6 | 3–5 alata nad podacima; testiranje iz Claude Desktopa | MCP protokol, dizajn alata |
| 2. Jedan agent | 5 | Agent petlja ručno: model → poziv alata → rezultat → ponovo | Kako agenti rade |
| 3. Multi-agent | 7 | Planer, paralelni istraživači, sintetizator, deljeno stanje | Orkestracija, paralelizam |
| 4. Evaluacija | 4 | Pokretanje eval seta (12 + pitanje sa 18 kompanija), ocena tačnosti i citata, poređenje sa jednim agentom | Eval, metrike |
| 5. UI i trace | 4 | Prikaz toka agenata u realnom vremenu | Streaming, observability |
| 6. Demo | 2 | README, dijagram arhitekture, video od 2 min, objava na GitHub-u | Prezentacija |

Evaluacija je dokaz za CV: konkretan rezultat tipa „multi-agent tačan u 8/10 naspram 5/10 za jednog agenta“.

**Obavezno:** paralelni agenti, eval sa 13 pitanja, UI.

**Samo ako ostane vremena:**
- proveravač brojeva i citata
- web pretraga samo za demo, isključena tokom evala

**Pravilo za izmene plana:** plan se menja samo ako nešto ne može da radi ili izmereni rezultat pokaže da je pristup pogrešan. Nove ideje idu na spisak „samo ako ostane vremena“ i ne ulaze u fazu koja je u toku.

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
  - [x] Model/SDK: DeepSeek V4.1 Flash preko **OpenRouter-a, zakucan na Alibaba Cloud provajdera** (`deepseek/deepseek-v4.1-flash`, `provider.only=["alibaba"]`, `allow_fallbacks=false`), `openai` Python SDK na `https://openrouter.ai/api/v1` (izmenjeno 2026-11-08; pre toga DeepSeek API direktno, a još ranije Qwen3 4B preko Ollame); `mcp` SDK za server i klijent
  - [x] Konvencija: FY = kalendarska godina u kojoj se fiskalna godina završava (polje `fy` iz EDGAR-a je nepouzdano)
  - [x] Eval set: 12 pitanja u `eval/questions.json` (3 činjenična, 4 uporedna, 3 sa objašnjenjem, 2 bez odgovora); svi odgovori provereni (brojevi iz XBRL, objašnjenja E1–E3 iz teksta 10-K MD&A)
  - [x] Jezik evala: engleski (`question_en`); srpski za UI/demo
- [x] Faza 1 — završena 2026-11-08 (teach-back urađen)
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
  - [x] Ručni test: MCP Inspector i Claude Desktop (2026-11-08, tim)
  - [x] Teach-back faze 1
- Handoff na drugi računar (2026-11-08): vidi `handoff.md`
- [x] Faza 2 — završena 2026-11-08 (teach-back preskočen, tim je prošao kod)
  - [x] `agents/single_agent.py` (ručna petlja) + `tests/test_single_agent.py` (lažni model)
  - [x] Teach-back petlje (2026-11-08)
  - [x] Prelazak na OpenRouter/Alibaba: `provider_options()` gradi parametre po provajderu, petlja vraća `reasoning_details` ili `reasoning_content` (ukupno 71 test, prolaze)
  - [x] Probati na pravom modelu: F1, C2, E3 (2026-11-08, OpenRouter/Alibaba, thinking isključen): **3/3 tačno**, svaki u 2 koraka, 2,7–4,8 s, ukupno ~$0,001
    - C2: model sam pozove alat 3 puta u jednom koraku (po kompaniji) i napomene da se fiskalne godine razlikuju
    - E3 sa thinking-om: 4 koraka, 5 pretraga, svih 5 ključnih tačaka (bez njega 4/5, fali $1,83B), ~3× više tokena, 9,6 s; vraćanje `reasoning_details` uz alate radi bez greške
    - **Odluka: thinking isključen za ceo eval, za oba sistema** (2026-11-08). Sa thinking-om `temperature=0` nema efekta, pa bi rezultati bili manje ponovljivi, a thinking dodatno jača jednog agenta
  - [x] Provera U1, U2, C4 (2026-11-08, thinking isključen):
    - U1 ✅ kaže da FY2030 ne postoji i ne procenjuje; citat `[INTC]` nije pravi `source_id` (kvalitet citata)
    - U2 ✅ ispravlja lažnu premisu (HD neto +14,806)
    - C4 ⚠️ svi brojevi i periodi tačni (zamka sa FY nije okinula), ali **pogrešan zaključak**: kaže „Lowe's stabilniji", a sam navodi da LOW ima veći raspon (2,3 naspram 1,6 p.p.) i veće promene iz godine u godinu
    - Prompt NE podešavamo prema ovim pitanjima (to bi bilo „učenje na ispitu"); greške ostaju da ih eval izmeri
    - Za fazu 3: jak model rešava ova pitanja u 2 koraka, pa će razliku multi-agenta pokazati teža pitanja (C4 sa zamkom, 13. pitanje sa 18 kompanija)
  - Zašto nije Ollama: `qwen3:4b` je na CPU-u potrošio ceo limit na razmišljanje (F1 i C2 bez poziva alata, E3 pogrešan odgovor; razmišljanje nismo mogli pouzdano da ugasimo)
- [ ] Faza 3 — u toku
  - Dizajn: `asyncio`, jedna MCP veza za sve agente
  - [x] `agents/multi_agent.py`: planer (bez alata, spisak kompanija u promptu, JSON plan, 2 pokušaja pa rezervni plan) → istraživači (`run_agent` sa svojim promptom, `asyncio.gather` + `Semaphore(6)`, pad jednog ne obara ostale) → sintetizator (bez alata, samo iz nalaza); `run_agent` dobio parametar `system_prompt`
  - [x] `tests/test_multi_agent.py` (lažni model po ulozi; dokazano da istraživači rade istovremeno nad jednom MCP vezom i da limit paralelizma radi; ukupno 85 testova, prolaze)
  - [x] Pravi model (2026-11-08, jedno pokretanje po pitanju):
    | | Jedan agent | Multi-agent |
    |---|---|---|
    | C2 | ✅ 3 poziva modela, 3,3k/0,5k tokena, 4,5 s | ✅ 8 poziva, 10,8k/1,0k tokena, 6,7 s |
    | C4 | ⚠️ tačni brojevi, pogrešan zaključak (LOW) | ✅ tačan zaključak (HD, raspon 1,6 naspram 2,3 p.p.), 6 poziva, 8,9k/2,0k tokena, 10,9 s |
    - Jedno pokretanje nije dokaz; eval (faza 4) meri na svim pitanjima
    - Primećeno: planer u podzadacima traži da istraživač „izračuna" maržu, iako je pravilo da se koriste izvedene metrike; istraživači su ipak uzeli maržu iz alata
- [ ] Faza 4
- [ ] Faza 5
- [ ] Faza 6

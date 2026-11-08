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
4. **Evaluacija**: 12 pitanja + posebno označeno 13. pitanje sa svih 18 kompanija + 3 teža pitanja (H1–H3, posebna kategorija); poređenje multi-agent sistema sa jednim agentom (tačnost, kvalitet citata).

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
| 4. Evaluacija | 4 | Pokretanje eval seta (12 + pitanje sa 18 kompanija + H1–H3), ocena tačnosti i citata, poređenje sa jednim agentom | Eval, metrike |
| 5. UI i trace | 4 | Prikaz toka agenata u realnom vremenu | Streaming, observability |
| 6. Demo | 2 | README, dijagram arhitekture, video od 2 min, objava na GitHub-u | Prezentacija |

Evaluacija je dokaz za CV: konkretan rezultat tipa „multi-agent tačan u 8/10 naspram 5/10 za jednog agenta“.

**Obavezno:** paralelni agenti, eval sa 13 pitanja + H1–H3, UI.

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
- [ ] Faza 4 — u toku
  - **Izmena plana 2026-11-08: dodata teža pitanja H1–H3** (posebna kategorija, glavni rezultat na 12 pitanja ostaje kako je definisan). Razlog je izmeren: jak model rešava postojeća pitanja u 2 koraka, pa razlika između sistema ne može da se vidi. Pravila da eval ostane pošten:
    - pitanja se biraju po principu (širina, brojevi + objašnjenja za više kompanija, više koraka zaključivanja), ne po rezultatu
    - pitanja i provereni odgovori se pišu PRE pokretanja bilo kog sistema; nijedno se ne izbacuje posle gledanja rezultata
    - bar jedno pitanje gde multi-agent verovatno gubi (H2: planer pravi plan unapred i ne zna koga treba pretražiti)
    - u izveštaju idu svi rezultati, i za 12 pitanja i za H; svako pitanje ~3 pokretanja
  - [x] Napisana i proverena iz podataka 4 nova pitanja (`eval/questions.json` v1.1, `"set": "extra"`; stara su `"set": "main"`, sadržaj nepromenjen), nijedan sistem još nije pokrenut na njima:
    - B1: najveće i najmanje neto marže FY2024 među svih 18 (NVDA, MSFT, TXN / INTC, BBY, MU)
    - H1: rast prihoda FY2024 i razlog iz 10-K za NVDA (+125,9%, Data Center), AMD (+13,7%, Data Center i Client), INTC (−2,1%, Altera/Mobileye i Foundry)
    - H2: najniža operativna marža u softveru FY2024 = NOW 12,4% (CRM 14,4%); rast troškova pre svega zbog zapošljavanja i troškova zaposlenih
    - H3: comparable sales LOW −2,7% / BBY −2,3%, prihod −3,1% / −4,4% (BBY prethodna godina imala 53. nedelju, ~$735M); zamka: Lowe's tu godinu zove „fiscal 2024", Best Buy „fiscal 2025"
  - [x] Način ocenjivanja: Claude ocenjuje naslepo (`to_grade.json` izmešan i anoniman, `key.json` otvoren tek posle ocena), po pravilima iz pitanja, 1 / 0,5 / 0, sa obrazloženjem; automatski: citati (važi samo ID koji je alat vratio u tom pokretanju), tokeni, vreme, cena, kontekst
  - [x] `eval/run_eval.py`, `eval/report.py`, `eval/metrics.py` (+ testovi, ukupno 96)
  - [x] **Eval 2026-11-08_1903** (16 pitanja × 2 sistema × 3 pokretanja, DeepSeek V4.1 Flash / Alibaba, thinking isključen), `eval/results/2026-11-08_1903/report.md`:
    | | Jedan agent | Multi-agent |
    |---|---|---|
    | Tačnost main (12) / extra (4) | 100% / 91,7% | 100% / 91,7% |
    | Stabilnost (ista ocena u 3 pokretanja) | 87,5% | 93,8% |
    | Vreme (prosek) | 5,8 s | 11,1 s |
    | Ulazni tokeni (prosek) | 6,5k | 18,8k |
    | Cena po tačnom odgovoru | $0,0007 | $0,0020 |
    | Najveći kontekst u 1 pozivu (max) | 6,9k | 9,5k |
    | Važeći citati | 99,5% | 97,5% (interni `[t1]` kod U1) |
    - **Zaključak: sa jakim modelom multi-agent NE donosi veću tačnost na ovom skupu, a košta ~3× više i traje ~2× duže.** Paralelizam radi (ubrzanje 1,98×), ali ne nadoknađuje dodatne pozive (planer + sintetizator)
    - Hipoteza „istraživači imaju kratak kontekst" nije potvrđena: najveći pojedinačni prompt je veći kod multi-agenta (sintetizator dobija sve nalaze)
    - Greške: jedan agent H1 jednom (pogrešan razlog za Intel) i H3 jednom (bez ukupnog comparable sales za BBY); multi-agent H3 dvaput (jednom upao u FY zamku za Lowe's, jednom istraživač stao na max_steps)
    - C4 je jedan agent u evalu rešio 3/3, iako je u ranijem pojedinačnom pokretanju pogrešio → pouka: jedno pokretanje nije dokaz
    - Ograničenja: plafon (skoro sve tačno, pitanja su laka za ovaj model); slepoća nije savršena (multi-agent odgovori ponekad pominju „researcher"/„findings"/`[t1]`); ocenjivač je isti asistent koji je napravio sistem → potrebna ljudska provera uzorka
  - [ ] Ljudska provera uzorka ocena (~15) i upis slaganja u izveštaj
  - [x] **Eval sa slabijim modelom: Gemma 4 26B A4B** (grana `eval-gemma-4-26b`, `eval/results/2026-11-08_1949/report.md`; DeepInfra fp8, thinking isključen, isti kod i pitanja):
    | | Jedan agent | Multi-agent |
    |---|---|---|
    | Tačnost main (12) / extra (4) / sve | 95,8% / **70,8%** / 89,6% | 91,7% / **91,7%** / 91,7% |
    | Vreme (prosek) | 6,5 s | 11,1 s |
    | Ulazni tokeni (prosek) | 8,1k | 12,1k |
    | Cena po tačnom odgovoru | $0,0008 | $0,0012 |
    | Najveći kontekst u 1 pozivu (max) | 7,8k | 4,5k |
    | Stop na max_steps | 3 (sve na B1) | 0 |
    - **Sa slabijim modelom multi-agent pobeđuje na težim pitanjima (+21 p.p.)**, ukupno +2 p.p.; na osnovnim pitanjima jedan agent je malo bolji (multi-agent jednom pogrešio zaključak na C4)
    - Razlika je skoro cela iz B1 (18 kompanija): Gemma kao jedan agent zove **jedan alat po koraku** i ne stigne do kraja za 10 koraka (0/3); DeepSeek je zvao više alata odjednom. Multi-agent: svaki istraživač 1 kompanija → 3/3. Zavisi i od našeg limita MAX_STEPS=10
    - Ovde se hipoteza o kratkom kontekstu POTVRĐUJE: najveći prompt 4,5k (multi) naspram 7,8k (jedan agent); kod DeepSeek-a je bilo obrnuto
    - Oba sistema na C1 daju samo godišnje stope umesto rasta FY2023→FY2025 (0,5 svima)
    - Provajder: Google Vertex spaja paralelne pozive alata u jedan neispravan (`{..}{..}{..}`) i daje 400 na istoriju sa neispravnim JSON-om; 9 drugih provajdera radi ispravno → DeepInfra. Petlja sada u istoriji menja neispravne argumente sa `{}` (ne utiče na DeepSeek eval: 0 grešaka alata)
    - Ograničenje: seme mešanja `to_grade.json` bilo je isto kao u DeepSeek evalu, pa su ID-evi mapirani isto (ocenjivač je za 4 odgovora znao sistem iz ranijeg ocenjivanja). Ispravljeno: seme sada zavisi od foldera
  - **Poređenje modela (glavna priča za CV):** sa jakim modelom (DeepSeek V4.1 Flash) multi-agent ne donosi tačnost, a košta ~3× više; sa slabijim modelom (Gemma 4 26B A4B) multi-agent rešava zadatke koje jedan agent ne može da završi (širina: 18 kompanija), uz ~1,6× veću cenu. Arhitektura sa više agenata vredi kad je model slabiji ili kad je zadatak širok
- [ ] Faza 5
- [ ] Faza 6

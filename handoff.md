# Handoff — nastavak rada na drugom računaru

Datum: 2026-11-08. Plan, pravila i status su u [`hakaton.md`](hakaton.md) — pročitati prvo.
Ovaj fajl dopunjuje `hakaton.md`: gde smo stali, kako podići okruženje i šta nije očigledno iz koda.

> **Za Claude Code na novom računaru:** pročitaj `hakaton.md` i ovaj fajl pre bilo čega.
> Komunikacija na srpskom. Ti pišeš kod, tim uči iz objašnjenja. Idi korak po korak i stani posle
> svakog koraka (tim je jednom zaustavio preskakanje: prvo podaci i provera, pa tek onda dalje).
> Pre većih izmena opiši plan i čekaj potvrdu. **Pre svakog commit-a i push-a pitaj s kog GitHub naloga**
> (tim koristi više naloga preko `gh auth switch`).

## Gde smo stali

- **Faze 0–4 su gotove.** MCP server (3 alata), jedan agent, multi-agent (planer → paralelni istraživači →
  sintetizator), eval na 16 pitanja sa dva modela, ocene naslepo, tim je proverio uzorak ocena.
- **Grane:** `main` ima faze 0–4 sa DeepSeek evalom. `eval-gemma-4-26b` dodaje Gemma eval, čišćenje
  argumenata u petlji i poređenje modela. **Tim je odlučio da se grana ne spaja za sada; rad se nastavlja na njoj.**
- **Faza 5 (UI) je urađena, čeka pregled tima.** `python -m web.server` (backend, :8000) + `cd web/ui; npm install;
  npm run dev` (frontend, :3000). Događaji iz `on_event` idu kroz SSE; frontend ih pretvara u ekran reducer-om (`web/ui/lib/useRun.ts`).
  `reactStrictMode` je isključen namerno (inače bi se agent pokretao dvaput), a `EventSource` se zatvara na `done`
  (inače se sam ponovo poveže i ponovo pokrene agenta).
- **Sledeće — Faza 6: demo** (README, dijagram, video od 2 min).
- **Samo ako ostane vremena:** B1 za jednog agenta sa većim `MAX_STEPS`; proverivač brojeva i citata; web pretraga za demo.

## Podešavanje na novom računaru (Windows, PowerShell)

```powershell
git clone https://github.com/StefanJ2004/MCP-server-multiagent-reasoning-solution.git
cd MCP-server-multiagent-reasoning-solution
git switch eval-gemma-4-26b     # grana na kojoj se radi
python -m venv .venv            # Python 3.11+ (razvijano na 3.13)
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env          # popuni SEC_USER_AGENT i OPENAI_API_KEY (OpenRouter ključ)
python scripts/download_data.py # ~100 MB, par minuta; data/raw/ NIJE u gitu
pytest -q                       # očekivano: 102 passed
```

Podaci se skidaju ponovo jer nisu u gitu: 18 `companyfacts` JSON-a (~70 MB) i 82 teksta 10-K izveštaja (~30 MB).
Bez njih testovi koji traže podatke budu preskočeni (skip), a ne oboreni. Proveri da piše **102 passed**, a ne "skipped".

**Model**: DeepSeek V4.1 Flash preko OpenRouter-a, zakucan na Alibaba Cloud. OpenRouter ključ u `.env` kao
`OPENAI_API_KEY` (nikad u git, repo je javan; ključ ima limit od $5). Ollama nije potrebna.

## Struktura i šta je gde

| Fajl | Šta radi |
|---|---|
| `mcp_server/financials.py` | XBRL → čisti godišnji brojevi: mapa tagova po prioritetu, dedup (najranija prijava), FY po kraju perioda, izvedene metrike |
| `mcp_server/search.py` | BM25 pisan ručno nad 10-K tekstom: prozori 150 reči / korak 110, sekcije iz naslova, Risk Factors ×0,5 |
| `mcp_server/server.py` | Tanak MCP sloj: 3 alata (`list_companies`, `get_financials`, `search_filing`), kompaktan JSON |
| `agents/single_agent.py` | Ručna petlja; `provider_options()` (parametri po provajderu), `returned_ids()` (za proveru citata), čišćenje neispravnih argumenata u istoriji |
| `agents/multi_agent.py` | Planer (bez alata, JSON plan) → istraživači (`run_agent` sa svojim promptom, `gather` + `Semaphore(6)`) → sintetizator |
| `eval/questions.json` | 16 pitanja: 12 `main` (F, C, E, U) + 4 `extra` (B1 svih 18 kompanija, H1–H3 teža), svi provereni |
| `eval/run_eval.py` | Oba sistema naizmenično, pun trag u `results.jsonl`, `to_grade.json` (anonimno) + `key.json` |
| `eval/report.py`, `eval/metrics.py` | Tačnost, stabilnost, vreme, tokeni, cena (`PRICES` po modelu), kontekst, važenje citata |
| `eval/results/2026-11-08_1903/` | DeepSeek eval (izveštaj, ocene, ključ, sirovi rezultati) |
| `eval/results/2026-11-08_1949/` | Gemma 4 26B A4B eval |
| `scripts/benchmark_ollama.py`, `data/benchmark/` | Zašto lokalni qwen3:4b nije izabran |
| `web/server.py`, `web/ui/` | Backend (Starlette, SSE) i frontend (Next.js) za prikaz uživo |
| `tests/` | 102 testa; agenti se testiraju lažnim modelom (`FakeLLM`, `RoleLLM` po ulozi), alati i podaci su pravi |

## Rezultat (ukratko, detalji u `hakaton.md` i `eval/results/*/report.md`)

| | DeepSeek V4.1 Flash: jedan / multi | Gemma 4 26B A4B: jedan / multi |
|---|---|---|
| Tačnost, 12 osnovnih | 100% / 100% | 95,8% / 91,7% |
| Tačnost, 4 teža | 91,7% / 91,7% | 70,8% / 91,7% |
| Cena po tačnom odgovoru | $0,0007 / $0,0020 | $0,0008 / $0,0012 |

Sa jakim modelom multi-agent ne vredi ~3× veće cene; sa slabijim modelom rešava širok zadatak (B1) koji jedan
agent ne završi u 10 koraka (Gemma zove jedan alat po koraku).

## Stvari koje nisu očigledne (naučeno na teži način)

**MCP SDK je 2.x (instalirano 2.3.0)**
- `from mcp.server.mcpserver import MCPServer`. **Ne** `from mcp.server.fastmcp import FastMCP` (to je 1.x, i većina primera na internetu je za 1.x).
- Klijent: `from mcp import Client, StdioServerParameters`. `Client(server_obj)` radi u istom procesu (brzi testovi), a `Client(StdioServerParameters(...))` pokreće pravi podproces. Ovo drugo koriste agenti. Jedna MCP veza može da služi više istraživača istovremeno.
- Docstring postaje opis alata; `Literal[...]` u tipu postaje `enum` u šemi.

**OpenRouter**
- Nestandardni parametri (`reasoning`, `provider`) idu kroz `extra_body`, iz `provider_options()`. Provajder se zakucava sa `OPENROUTER_PROVIDER` (`only` + `allow_fallbacks: false`), da eval zna ko je odgovarao; agent loguje `model` i `provider` iz svakog odgovora.
- **Provajder može da pokvari pozive alata.** Gemma na Google Vertex-u spaja više poziva u jedan (`{..}{..}{..}`) i vraća 400 kad u istoriji vidi neispravan JSON. Pre evala sa novim modelom proveri provajdere jednim upitom koji traži više alata odjednom.
- Thinking je **isključen** za ceo eval (ponovljivost; sa thinking-om `temperature=0` nema efekta).

**Eval**
- Pitanja i odgovori se pišu i proveravaju PRE pokretanja sistema; ništa se ne izbacuje posle gledanja rezultata.
- Ocenjivač ne otvara `key.json` pre upisa `grades.json`. Seme mešanja zavisi od foldera (u Gemma evalu je bilo isto kao u DeepSeek-u, to je navedeno kao ograničenje).
- Jedno pokretanje nije dokaz: jedan agent je C4 pogrešio u probi, a u evalu ga je rešio 3/3.

**Zamke u EDGAR podacima** (rešava server, model ih ne vidi)
- Isti period se ponavlja kroz više 10-K prijava. Uzima se **najranija** prijava.
- Polje `fy` je nepouzdano. **FY = kalendarska godina u kojoj fiskalna godina završava** (HD godina do 2025-02-02 je FY2025, iako je HD zove "fiscal 2024"; Best Buy istu godinu zove "fiscal 2025").
- Ista metrika pod više tagova: važi **redosled tagova** (`NetIncomeLoss` pre `ProfitLoss`), nikad min/max.
- Godišnje = 10-K i trajanje 350–380 dana (53-nedeljne godine postoje).

**Rizik arhitekture (upisan u `hakaton.md`)**: planer pravi plan pre nego što vidi podatke, pa na pitanjima tipa
„top 3 po sektoru“ bira kompanije proizvoljno (izmereno: multi-agent 3/10, jedan agent 9/10). Ne dodaje se u eval.

**BM25**: odličan za konkretne termine, loš za neodređena pitanja; zato opis alata i prompt traže konkretne termine.

**Windows konzola** je cp1252: pokretati sa `PYTHONIOENCODING=utf-8` (bez `python -I`).

## Odluke koje ne treba ponovo otvarati

- Domen SEC EDGAR, Python, 18 kompanija, FY2022+.
- Glavni model: DeepSeek V4.1 Flash preko OpenRouter-a (Alibaba). Drugi model za poređenje: Gemma 4 26B A4B (DeepInfra).
- Bez frameworka za agent petlju i MCP alate: mehanika mora da se vidi u kodu.
- Samo `get_financials`, bez `compare_companies`, da poređenje rade agenti.
- Eval na engleskom, isti model i podešavanja za oba sistema, thinking isključen, ocenjivanje naslepo + ljudska provera uzorka.
- Plan (`hakaton.md`) se menja samo kad nešto ne radi ili merenje pokaže da je pristup pogrešan.

# Handoff — nastavak rada na drugom računaru

Datum: 2026-11-08. Plan, pravila i status su u [`hakaton.md`](hakaton.md) — pročitati prvo.
Ovaj fajl dopunjuje `hakaton.md`: gde smo stali, kako podići okruženje i šta nije očigledno iz koda.

> **Za Claude Code na novom računaru:** pročitaj `hakaton.md` i ovaj fajl pre bilo čega.
> Komunikacija na srpskom. Ti pišeš kod, tim uči iz objašnjenja. Idi korak po korak i stani posle
> svakog koraka (tim je jednom zaustavio preskakanje: prvo podaci i provera, pa tek onda dalje).
> Pre većih izmena opiši plan i čekaj potvrdu.

## Gde smo stali

- **Faza 0**: gotova (domen, 18 kompanija, eval set od 12 proverenih pitanja).
- **Faza 1 (MCP server)**: gotova, uključujući ručni test i teach-back.
- **Sledeće — Faza 2**: jedan agent, ručna petlja `model → tool_call → MCP alat → rezultat → model`
  sa DeepSeek V4.1 Flash preko **OpenRouter-a, zakucanog na Alibaba Cloud**. Kod je u `agents/single_agent.py`, ali **još nije probao pravi model**.
  Prvi korak: upisati OpenRouter ključ kao `OPENAI_API_KEY` u `.env`, pa probati F1, C2 i E3 (`python -m agents.single_agent --id F1`).
  U ispisu `[model]` proveriti da je `provider=Alibaba`.
  Uspeh: sva tri stižu do odgovora, a bar dva su tačna. Zvaničnu cenu proveriti pre uplate.

## Podešavanje na novom računaru (Windows, PowerShell)

```powershell
git clone https://github.com/StefanJ2004/MCP-server-multiagent-reasoning-solution.git
cd MCP-server-multiagent-reasoning-solution
python -m venv .venv            # Python 3.11+ (razvijano na 3.13)
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env          # popuni SEC_USER_AGENT: "Ime Prezime email@domen.com" (SEC to traži)
python scripts/download_data.py # ~100 MB, par minuta; data/raw/ NIJE u gitu
pytest -q                       # očekivano: 71 passed
```

Podaci se skidaju ponovo jer nisu u gitu: 18 `companyfacts` JSON-a (~70 MB) i 82 teksta 10-K izveštaja (~30 MB).
Bez njih testovi koji traže podatke budu preskočeni (skip), a ne oboreni. Proveri da piše **71 passed**, a ne "skipped".

**Model**: DeepSeek V4.1 Flash preko OpenRouter-a (Alibaba Cloud); OpenRouter ključ upisati u `.env` kao `OPENAI_API_KEY` (nikad u git, repo je javan). Ollama više nije potrebna.

## Struktura i šta je gde

| Fajl | Šta radi |
|---|---|
| `mcp_server/companies.py` | 18 tikera → sektor; `FIRST_FISCAL_YEAR = 2022` |
| `mcp_server/financials.py` | XBRL → čisti godišnji brojevi: mapa tagova po prioritetu, dedup (najranija prijava), FY po kraju perioda, izvedene metrike |
| `mcp_server/search.py` | BM25 pisan ručno nad 10-K tekstom: prozori 150 reči / korak 110, sekcije iz naslova, Risk Factors ×0,5 |
| `mcp_server/server.py` | Tanak MCP sloj: 3 alata (`list_companies`, `get_financials`, `search_filing`), kompaktan JSON |
| `scripts/download_data.py` | Skida companyfacts + 10-K tekstove, pravi `data/raw/filings/manifest.json` |
| `scripts/exploration/` | Skripte iz faze 0, samo referenca (`values.py` ima poznat bag sa min, vidi README tamo) |
| `eval/questions.json` | 12 pitanja (F1–F3 činjenična, C1–C4 uporedna, E1–E3 objašnjenja, U1–U2 bez odgovora) sa proverenim odgovorima |
| `tests/` | `test_financials.py`, `test_search.py`, `test_server.py` (uključuje stdio podproces), `test_single_agent.py` (lažni model) |
| `agents/single_agent.py` | Ručna agent petlja (faza 2); ovde ide i faza 3 |

## Stvari koje nisu očigledne (naučeno na teži način)

**MCP SDK je 2.x (instalirano 2.3.0)**
- `from mcp.server.mcpserver import MCPServer`. **Ne** `from mcp.server.fastmcp import FastMCP` (to je 1.x, i većina primera na internetu je za 1.x).
- Klijent: `from mcp import Client, StdioServerParameters`. `Client(server_obj)` radi u istom procesu (brzi testovi), a `Client(StdioServerParameters(command=..., args=["-m","mcp_server.server"]))` pokreće pravi podproces. Ovo drugo koristi agent.
- `call_tool(...)` vraća `.content[0].text` i `.is_error`.
- Docstring postaje opis alata; `Literal[...]` u tipu postaje `enum` u šemi. Pogrešan enum daje `is_error` sa spiskom dozvoljenih vrednosti.
- `pyproject.toml` zato traži `mcp>=2.3,<3`.

**`openai` SDK** (3.46.0) se koristi kao klijent za OpenRouter (`OPENAI_BASE_URL=https://openrouter.ai/api/v1`,
`MODEL=deepseek/deepseek-v4.1-flash`, `OPENROUTER_PROVIDER=alibaba`). Parametri koji nisu standardni OpenAI
(`reasoning`, `provider` na OpenRouter-u; `thinking` na DeepSeek API-ju) prave se u `provider_options()` i šalju kroz `extra_body`.
Uz alate se razmišljanje vraća u narednim zahtevima: `reasoning_details` (OpenRouter) ili `reasoning_content` (DeepSeek direktno).

**Zamke u EDGAR podacima** (rešava server, model ih ne vidi)
- Isti period se ponavlja kroz više 10-K prijava. Uzima se **najranija** prijava (originalni 10-K).
- Polje `fy` je godina prijave, ne perioda, i ume da bude pogrešno (CRM). Zato: **FY = kalendarska godina u kojoj fiskalna godina završava** (HD godina koja se završava 2025-02-02 je FY2025, iako je HD zove "fiscal 2024").
- Ista metrika postoji pod više tagova. Važi **redosled tagova** (`NetIncomeLoss` pre `ProfitLoss`), nikad min/max. Bag sa min je dao pogrešan INTC neto (−19.233 umesto −18.756).
- Godišnje = forma 10-K i trajanje 350–380 dana (postoje 53-nedeljne godine, npr. HD FY2025).
- `submissions` API u `recent` drži samo ~1000 prijava, a starije su u `filings.files` stranicama (zbog toga su CRM 10-K izveštaji isprva falili).

**BM25 ograničenje**: odličan za konkretne termine ("valuation allowance", "inventory write-down"),
loš za neodređena pitanja ("reasons for loss"). Zato opis alata `search_filing` traži konkretne termine.
**Prompt istraživača u fazi 2/3 mora da kaže isto:** konkretni termini, više pretraga sa različitim rečima.

**Windows konzola** je cp1252, pa `print` teksta iz 10-K može da pukne na Unicode. Pokretati sa
`PYTHONIOENCODING=utf-8` (i bez `python -I`, jer `-I` ignoriše PYTHON* promenljive).

## Odluke koje ne treba ponovo otvarati

- Domen SEC EDGAR, Python, 18 kompanija, FY2022+.
- DeepSeek V4.1 Flash preko OpenRouter-a, zakucan na Alibaba Cloud (2026-11-08; umesto DeepSeek API-ja direktno i lokalnog Qwen3 4B preko Ollame).
- Plan je zaključan 2026-11-08 (`hakaton.md`): bez web pretrage u eval sistemu, eval sa 13 pitanja.
- Bez frameworka za agent petlju i MCP alate: mehanika mora da se vidi u kodu.
- Samo `get_financials`, **bez `compare_companies`**, da poređenje rade agenti (prednost multi-agenta na uporednim pitanjima).
- Brojevi u milijardama USD sa decimalama. Izvedene metrike računa server.
- Eval na engleskom (`question_en`), isti model za jednog agenta i multi-agent. Način ocenjivanja: **još nije odlučeno** (faza 4).

## Plan za fazu 2 (predlog, nije počet)

1. **Model**: DeepSeek API, parametri u `README.md`.
2. **MCP klijent u agentu**: pokreće `mcp_server.server` preko stdio-a, `list_tools()`, pa prevodi MCP šeme u OpenAI `tools` format.
3. **Agent petlja** (`agents/single_agent.py`): poruke → `chat.completions.create(tools=...)` → ako ima `tool_calls`, pozovi MCP alat, dodaj `role: tool` poruku i ponovi; inače kraj. Ograničenje broja koraka.
4. **System prompt**: citiraj `source_id`/`passage_id`, ne izmišljaj, konkretni termini za pretragu. `finish_reason=length` je greška.
5. Ručno probati na 2–3 eval pitanja (npr. F1, C2, E3) i ispraviti prompt/opise alata.

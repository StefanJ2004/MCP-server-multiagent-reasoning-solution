# Multi-agent istraživač nad SEC EDGAR podacima

MCP server izlaže finansijske podatke 18 američkih kompanija (XBRL brojevi + tekst 10-K izveštaja),
a multi-agent sistem (planer → paralelni istraživači → sintetizator) odgovara na pitanja sa citatima.
Rezultat se poredi sa jednim agentom na eval setu od 16 pitanja (`eval/questions.json`), sa dva modela.

Plan i status: [`hakaton.md`](hakaton.md).

## Struktura

```
mcp_server/   MCP server i alati nad podacima
agents/       agent petlja, planer, istraživači, sintetizator
web/          backend (server.py, SSE) i frontend (ui/, Next.js)
eval/         pitanja, pokretanje evala, metrike, izveštaji (eval/results/<datum_vreme>/)
scripts/      skidanje podataka; scripts/exploration/ = skripte iz faze 0 (referenca)
data/raw/     skinuti podaci (nije u gitu)
tests/
```

## Podešavanje (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env      # pa popuni SEC_USER_AGENT
python scripts/download_data.py
```

## MCP server

Tri alata (`mcp_server/server.py`): `list_companies`, `get_financials`, `search_filing`.

```powershell
pytest -q                                  # svi testovi, ukljucujuci server preko stdio-a
python -m mcp_server.server                # pokretanje servera (stdio; ceka klijenta)
```

**MCP Inspector** (web UI za rucno pozivanje alata, treba Node):

```powershell
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe -m mcp_server.server
```

**Claude Desktop**: u `%APPDATA%\Claude\claude_desktop_config.json` dodaj (putanja do svog projekta),
pa restartuj Claude Desktop:

```json
{
  "mcpServers": {
    "sec-edgar": {
      "command": "C:\\Users\\Korisnik\\hakaton\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

## Model

| Podešavanje | Vrednost |
|---|---|
| Provajder | OpenRouter, zakucan na **Alibaba Cloud** (`OPENROUTER_PROVIDER=alibaba`, bez prebacivanja na druge provajdere); ključ u `.env`, `OPENAI_API_KEY` |
| Model | `deepseek/deepseek-v4.1-flash` (DeepSeek V4.1 Flash) |
| Endpoint | `https://openrouter.ai/api/v1` (OpenAI-kompatibilan) |
| Cena (Alibaba, 2026-11-08) | $0,075 / 1M ulaznih, $0,30 / 1M izlaznih tokena |
| Temperatura | 0 (ima efekat samo kad je razmišljanje isključeno) |
| Izlaz po koraku | Najviše 8192 tokena; agent `finish_reason=length` tretira kao grešku |
| Thinking | `THINKING=disabled` u `.env`; ako je `enabled`, razmišljanje se vraća u sledećim zahtevima (`reasoning_details` na OpenRouter-u, `reasoning_content` na DeepSeek API-ju) |

Parametri koji se razlikuju po provajderu prave se u `provider_options()` (`agents/single_agent.py`).
DeepSeek API direktno i dalje radi: promeni `OPENAI_BASE_URL` i `MODEL` (vidi `.env.example`).
Agent loguje `model` i `provider` iz svakog odgovora, da se vidi ko je stvarno odgovorio.

Eval se pokreće na engleskom (`question_en`), istim modelom za jednog agenta i za multi-agent sistem.

## Agenti

```powershell
python -m agents.single_agent --id F1          # jedan agent (pitanje iz evala)
python -m agents.multi_agent --id C4           # planer -> paralelni istrazivaci -> sintetizator
python -m agents.multi_agent "Compare revenue of NVDA and AMD in FY2024."
```

## UI (uživo)

Dva terminala, iz root foldera:

```powershell
python -m web.server                 # backend: http://localhost:8000 (agenti + SSE tok događaja)
cd web/ui; npm install; npm run dev  # frontend: http://localhost:3000
```

Pitanje (ili izbor iz evala) → režim **Jedan agent / Multi-agent / Uporedo** → **Pokreni**. Uživo se vidi planer,
istraživači u paralelnim kolonama (svaki poziv modela i alata), sintetizator i odgovor. Citati su dugmići:
zeleni = taj izvor je vratio alat u ovom pokretanju, crveni = nije; klik prikazuje tačan pasus iz 10-K izveštaja.
Ispod odgovora: vreme, pozivi modela i alata, tokeni, najveći kontekst, cena (iste metrike kao u evalu).

Backend (`web/server.py`, Starlette, bez novih paketa) šalje događaje iz `on_event` kroz SSE; frontend
(`web/ui`, Next.js) ih pretvara u stanje ekrana reducer-om (`web/ui/lib/useRun.ts`).

## Eval

```powershell
python eval/run_eval.py                        # 16 pitanja x 2 sistema x 3 pokretanja -> eval/results/<datum_vreme>/
python eval/report.py eval/results/<folder>    # izveštaj (report.md); bez grades.json samo automatske metrike
```

Model za eval se menja bez izmene `.env`, npr.
`$env:MODEL="google/gemma-4-26b-a4b-it"; $env:OPENROUTER_PROVIDER="deepinfra"` pa `python eval/run_eval.py`.
Cene modela su u `eval/metrics.py` (`PRICES`).

Ocenjivanje: `run_eval.py` pravi `to_grade.json` (odgovori izmešani i anonimni) i `key.json` (koji je koji sistem).
Ocene (1 / 0,5 / 0, sa obrazloženjem, po pravilima iz pitanja) idu u `grades.json` pre otvaranja ključa.
Citat važi samo ako je taj `source_id` / `passage_id` vratio alat u istom pokretanju (provera je automatska).

| | DeepSeek V4.1 Flash: jedan / multi | Gemma 4 26B A4B: jedan / multi |
|---|---|---|
| Tačnost, 12 osnovnih | 100% / 100% | 95,8% / 91,7% |
| Tačnost, 4 teža (B1, H1–H3) | 91,7% / 91,7% | 70,8% / 91,7% |
| Cena po tačnom odgovoru | $0,0007 / $0,0020 | $0,0008 / $0,0012 |
| Vreme po pitanju | 5,8 s / 11,1 s | 6,5 s / 11,1 s |

Sa jakim modelom multi-agent ne donosi tačnost, a košta ~3× više. Sa slabijim modelom rešava širok zadatak
(B1, 18 kompanija) koji jedan agent ne završi u 10 koraka. Detalji i ograničenja: `eval/results/*/report.md`
i odeljak Faza 4 u `hakaton.md`.

Napomena o provajderu: Gemma na Google Vertex-u spaja više poziva alata u jedan neispravan poziv, pa se koristi DeepInfra.

## Ograničenja i rizici

**Planer pravi plan pre nego što vidi podatke.** Planer dobija samo spisak kompanija i deli posao unapred,
bez alata. Zato ne može dobro da reši pitanja tipa „prvo nađi, pa onda istraži“ (npr. „top 3 kompanije po
sektoru“): ne zna koje su to kompanije dok ne vidi brojke, pa bira proizvoljno.
- Izmereno 2026-11-08 (DeepSeek V4.1 Flash, van eval seta): pitanje *„compare the top 3 companies from every
  group and tell me which one is the most profitable“*. Planer je uzeo prve 3 kompanije sa spiska u svakom
  sektoru, propustio Micron i odgovorio „NVIDIA“ (tačno: Micron po neto marži 63,8%, Microsoft po iznosu
  $133,7B). Pri tome 36 poziva modela, 60 poziva alata, $0,0147, 31 s. Jedan agent je uzeo svih 18 kompanija
  i odgovorio tačno: 3 poziva modela, $0,0016, 16 s. Ocena: jedan agent 9/10, multi-agent 3/10.
- Na H2 iz evala (isti tip pitanja) do greške nije došlo, jer je planer poslao istraživače na svih 5
  softverskih kompanija; rizik se javlja kad planer mora da bira podskup.
- Moguće rešenje (nije urađeno): planer prvo pozove `get_financials` za rangiranje, pa tek onda deli posao
  (plan u dva koraka), ili istraživači mogu da vrate zahtev za novim podzadatkom.
- Pitanje namerno NIJE dodato u eval: izabrano je posle gledanja rezultata, pa bi naginjalo protiv multi-agenta.

Ostalo: pitanja u evalu su za jak model uglavnom laka (plafon); razlika na B1 zavisi i od limita od 10 koraka
(`MAX_STEPS`); ocenjivao je Claude naslepo, a tim je proverio uzorak. Detalji u `hakaton.md`.

## Konvencije

- **FY** = kalendarska godina u kojoj se fiskalna godina završava (polje `fy` iz EDGAR-a se ne koristi).
- Kad metrika postoji pod više XBRL tagova, važi redosled tagova (npr. `NetIncomeLoss` pre `ProfitLoss`).

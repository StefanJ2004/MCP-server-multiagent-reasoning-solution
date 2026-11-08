# Multi-agent istraživač nad SEC EDGAR podacima

MCP server izlaže finansijske podatke 18 američkih kompanija (XBRL brojevi + tekst 10-K izveštaja),
a multi-agent sistem (planer → paralelni istraživači → sintetizator) odgovara na pitanja sa citatima.
Rezultat se poredi sa jednim agentom na eval setu od 12 pitanja (`eval/questions.json`).

Plan i status: [`hakaton.md`](hakaton.md).

## Struktura

```
mcp_server/   MCP server i alati nad podacima
agents/       agent petlja, planer, istraživači, sintetizator
eval/         eval pitanja i (kasnije) skripta za ocenjivanje
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
| Runtime | Ollama, samo CPU |
| Model | `qwen3:4b` (`ollama pull qwen3:4b`) |
| Endpoint | `http://localhost:11434/v1` (OpenAI-kompatibilan) |
| Kontekst (`num_ctx`) | TBD posle benchmarka (cilj ~8192) |
| Temperatura | TBD |

Eval se pokreće na engleskom (`question_en`), istim modelom za jednog agenta i za multi-agent sistem.

## Konvencije

- **FY** = kalendarska godina u kojoj se fiskalna godina završava (polje `fy` iz EDGAR-a se ne koristi).
- Kad metrika postoji pod više XBRL tagova, važi redosled tagova (npr. `NetIncomeLoss` pre `ProfitLoss`).

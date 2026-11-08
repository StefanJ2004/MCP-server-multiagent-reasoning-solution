# Skripte iz faze 0 (samo referenca)

Brzo pisane skripte kojima smo istražili EDGAR podatke. Ne koriste se u sistemu.

- `coverage.py` - provera koje metrike postoje za koje kompanije (mapa tagova `TAGS`)
- `values.py` - godišnje vrednosti po periodu, detekcija konflikata među prijavama
- `fetch_10k.py` - skidanje jednog 10-K i HTML -> tekst

Poznata greška (pouka za MCP server): `values.py` kod više tagova uzima najmanju vrednost umesto da poštuje redosled tagova.

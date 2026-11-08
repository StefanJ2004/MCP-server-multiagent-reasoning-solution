"""Kompanije izabrane u fazi 0 (sve imaju kompletne metrike za FY2022+)."""

COMPANIES: dict[str, str] = {
    # cipovi
    "NVDA": "semiconductors", "AMD": "semiconductors", "INTC": "semiconductors",
    "AVGO": "semiconductors", "TXN": "semiconductors", "MU": "semiconductors",
    "AMAT": "semiconductors", "ADI": "semiconductors", "LRCX": "semiconductors",
    # softver
    "MSFT": "software", "CRM": "software", "ADBE": "software",
    "NOW": "software", "CSCO": "software",
    # maloprodaja
    "HD": "retail", "LOW": "retail", "BBY": "retail", "DG": "retail",
}

FIRST_FISCAL_YEAR = 2022

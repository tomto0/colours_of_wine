from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

# .env Datei laden
from dotenv import load_dotenv
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)

# ======================= Gemini / Google Generative AI =======================

GEMINI_MODEL_ENV = os.getenv("GEMINI_MODEL", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_KEY_SET = bool(GEMINI_API_KEY)

# Bevorzugte Modelle, falls GEMINI_MODEL nicht explizit gesetzt ist
PREFERRED_MODELS: List[str] = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-8b-latest",
]

# ======================= Google Custom Search ===============================

GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()

# Ist die Websuche korrekt konfigur iert?
SEARCH_ENABLED: bool = bool(GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID)

# ======================= DuckDuckGo / Suche =================================

DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

# ======================= Farben / Color Table ===============================

COLOR_TABLE: Dict[str, str] = {
    "pale straw": "#F6F2AF",
    "straw": "#F5EB7C",
    "gold": "#E6C75B",
    "amber": "#D48A3A",
    "rosé": "#F4A6B0",
    "salmon": "#F2A29B",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
    "tawny": "#A0522D",
}

# ======================= Heuristik-Konstanten ===============================

COUNTRIES: List[str] = [
    "Austria",
    "Germany",
    "France",
    "Italy",
    "Spain",
    "Portugal",
    "USA",
    "Australia",
    "New Zealand",
    "South Africa",
    "Chile",
    "Argentina",
]

# (Variety, typical wine_type)
VARIETIES: List[Tuple[str, str]] = [
    ("Riesling", "white"),
    ("Grüner Veltliner", "white"),
    ("Sauvignon Blanc", "white"),
    ("Chardonnay", "white"),
    ("Pinot Grigio", "white"),
    ("Gewürztraminer", "white"),
    ("Pinot Noir", "red"),
    ("Sangiovese", "red"),
    ("Nebbiolo", "red"),
    ("Cabernet Sauvignon", "red"),
    ("Merlot", "red"),
    ("Syrah", "red"),
    ("Zweigelt", "red"),
    ("Blaufränkisch", "red"),
    ("St. Laurent", "red"),
]

WINE_TYPES: List[str] = ["red", "white", "rosé", "sparkling"]

# Grundlegende Süße-Level (hauptsächlich deutschsprachig)
SWEETNESS_LEVELS: List[str] = [
    "trocken",
    "feinherb",
    "halbtrocken",
    "lieblich",
    "süß",
]

# Schlüsselwörter für Holz / Fassausbau
OAK_KEYWORDS: List[str] = [
    "barrique",
    "oak",
    "Holzfass",
    "Holz",
    "Eiche",
    "Eichenfass",
]

# Schlüsselwörter für Schaumwein
SPARKLING_KEYWORDS: List[str] = [
    "Sekt",
    "Champagner",
    "Crémant",
    "Frizzante",
    "Spumante",
    "Prosecco",
    "sparkling",
    "sparkling wine",
    "bubbles",
    "perlage",
]

# ======================= Backwards-Compat für heuristics.py =================
# heuristics.py importiert: SWEET_WORDS, SPARK_WORDS, OAK_WORDS
# SWEET_WORDS ist (Suchwort im Text, normalisierte Ausgabe)

SWEET_WORDS: List[Tuple[str, str]] = [
    ("trocken", "dry"),
    ("feinherb", "off-dry"),
    ("halbtrocken", "semi-dry"),
    ("lieblich", "semi-sweet"),
    ("süß", "sweet"),

    ("dry", "dry"),
    ("off-dry", "off-dry"),
    ("semi-dry", "semi-dry"),
    ("semi sweet", "semi-sweet"),
    ("sweet", "sweet"),
]

SPARK_WORDS: List[str] = SPARKLING_KEYWORDS
OAK_WORDS: List[str] = OAK_KEYWORDS

# ======================= Priorisierte Quellen ===============================

PRIORITY_SOURCES: List[Dict[str, Any]] = [
    {"id": "producer", "label": "Weingut / Erzeuger", "domains": [], "type": "producer"},
    {"id": "vinum", "label": "Vinum", "domains": ["vinum.eu", "vinum.de"]},
    {"id": "falstaff", "label": "Falstaff", "domains": ["falstaff.com", "falstaff.at", "falstaff.de"]},
    {"id": "meininger", "label": "Meininger Verlag", "domains": ["meininger.de"]},
    {"id": "eichelmann_gm", "label": "Eichelmann & Gault-Millau", "domains": ["gaultmillau.de", "gmverlag.de"]},
    {"id": "lobenberg", "label": "Lobenberg", "domains": ["lobenbergs.de"]},
    {"id": "vivino", "label": "Vivino", "domains": ["vivino.com"]},
    {"id": "weinplus", "label": "Wein.plus", "domains": ["wein.plus"]},
    {"id": "decanter", "label": "Decanter Magazin", "domains": ["decanter.com"]},
    {"id": "wineenthusiast", "label": "Wine Enthusiast", "domains": ["winemag.com"]},
    {"id": "weinandco", "label": "Wein & Co Österreich", "domains": ["weinco.at"]},
    {"id": "vinous", "label": "Antonio Galloni / Vinous", "domains": ["vinous.com"]},
    {"id": "jamessuckling", "label": "James Suckling", "domains": ["jamessuckling.com"]},
    {"id": "wineadvocate_de", "label": "Stephan Reinhardt / Wine Advocate (DE)", "domains": ["robertparker.com"]},
    {"id": "wineadvocate", "label": "Robert M. Parker jr. / The Wine Advocate", "domains": ["robertparker.com"]},
    {"id": "hughjohnson", "label": "Hugh Johnson", "domains": []},
    {"id": "jancis", "label": "Jancis Robinson", "domains": ["jancisrobinson.com"]},
    {"id": "pigott", "label": "Stuart Pigott", "domains": []},
    {"id": "gabriell", "label": "René Gabriell", "domains": []},
    {"id": "priewe", "label": "Jens Priewe", "domains": []},
    {"id": "veronelli", "label": "Veronelli", "domains": []},
    {"id": "halliday", "label": "James Halliday (Australien)", "domains": ["winecompanion.com.au"]},
]

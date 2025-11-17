from __future__ import annotations

import os
from typing import List, Tuple, Dict, Any

# ======================= Gemini / Google Generative AI =======================

GEMINI_MODEL_ENV = os.getenv("GEMINI_MODEL", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_KEY_SET = bool(GOOGLE_API_KEY)

# Bevorzugte Modelle, falls GEMINI_MODEL nicht explizit gesetzt ist
PREFERRED_MODELS: List[str] = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-8b-latest",
]

# ======================= DuckDuckGo / Suche =================================

DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

# ======================= Farben / Color Table ===============================

COLOR_TABLE: Dict[str, str] = {
    "pale straw": "#F6F2AF",
    "rosé": "#F4A6B0",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
}

# ======================= Heuristik-Konstanten ===============================

COUNTRIES = [
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

SWEET_WORDS = [
    ("trocken", "dry"),
    ("dry", "dry"),
    ("halbtrocken", "off-dry"),
    ("off-dry", "off-dry"),
    ("lieblich", "medium-sweet"),
    ("semi-sweet", "medium-sweet"),
    ("süß", "sweet"),
    ("sweet", "sweet"),
]

SPARK_WORDS = [
    "sparkling",
    "sekt",
    "champagne",
    "cava",
    "prosecco",
    "spumante",
    "frizzante",
]

OAK_WORDS = ["oak", "barrique", "oak-aged", "holzfass", "eiche", "eichenfass"]

# ======================= Quellen-Priorität ==================================

# Reihenfolge nach deiner Vorgabe:
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

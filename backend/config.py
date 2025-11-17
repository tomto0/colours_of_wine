import os
from typing import List, Tuple

# ========== Gemini / Google Generative AI ==========

GEMINI_MODEL_ENV = os.getenv("GEMINI_MODEL", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_KEY_SET = bool(GOOGLE_API_KEY)

PREFERRED_MODELS: List[str] = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-8b-latest",
]

# ========== DuckDuckGo ==========

DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

# ========== Farben / Color Table ==========

COLOR_TABLE = {
    "pale straw": "#F6F2AF",
    "rosé": "#F4A6B0",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
}

# ========== Such-Prioritäten ==========

PREFERRED_DOMAINS = [
    "vivino.com",
    "wine.com",
    "winesearcher.com",
    "cellartracker.com",
    "wein.plus",
    "falstaff.com",
    "weinfeder.de",
    "winelibrary.com",
    "wikipedia.org",
    "weingueter.de",
    "weingut",
    "winery",
]

# ========== Heuristik-Konstanten ==========

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

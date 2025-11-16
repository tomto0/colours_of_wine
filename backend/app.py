# backend/app.py
from __future__ import annotations

"""
Colours of Wine API backend.

This service:
- Takes a free-form wine name (e.g. "Riesling Bürklin-Wolf 2021"),
- Uses DuckDuckGo Search (ddgs) to fetch context,
- Extracts structured properties (country, grape, alcohol, …) via regex heuristics,
- Optionally sends snippets + name to Gemini (Google Generative AI) to fill in missing fields
  and generate a visualization profile for the frontend,
- Returns a clean JSON `AnalyzeResponse` for the FE.
"""

import os
import re
import json
import ast
from typing import List, Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ======================= Gemini (Google Generative AI) =======================

# Environment / configuration for Gemini
GEMINI_MODEL_ENV = os.getenv("GEMINI_MODEL", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_KEY_SET = bool(GOOGLE_API_KEY)

# Ordered preference of models if no explicit GEMINI_MODEL is set
PREFERRED_MODELS = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-8b-latest",
]

_genai = None
try:
    # Optional dependency – if not installed, LLM functionality will be disabled
    import google.generativeai as genai  # type: ignore
    _genai = genai
    if GEMINI_KEY_SET:
        _genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    # If anything goes wrong here, we quietly disable Gemini support
    _genai = None


def build_gemini() -> Tuple[Optional[Any], Optional[str]]:
    """
    Build and return a configured Gemini GenerativeModel instance plus the chosen model name.

    Selection strategy:
      1. Use explicitly configured GEMINI_MODEL if available and supported.
      2. Otherwise iterate through PREFERRED_MODELS.
      3. Otherwise, fall back to the first available model supporting 'generateContent'.
      4. If anything fails, return (None, None).
    """
    if not (_genai and GEMINI_KEY_SET):
        return None, None

    try:
        # List all available models once, then filter the ones that support `generateContent`.
        available = list(_genai.list_models())
        available_gc = {
            m.name
            for m in available
            if hasattr(m, "supported_generation_methods")
               and "generateContent" in getattr(m, "supported_generation_methods", [])
        }

        # Candidate model names in priority order
        candidates: List[str] = []
        if GEMINI_MODEL_ENV:
            candidates.append(GEMINI_MODEL_ENV)
        candidates.extend([m for m in PREFERRED_MODELS if m != GEMINI_MODEL_ENV])

        def is_available(name: str) -> Optional[str]:
            """
            Return the fully qualified model name if `name` or `models/name` exists;
            otherwise return None.
            """
            if name in available_gc:
                return name
            short = f"models/{name}"
            if short in available_gc:
                return short
            return None

        # Try configured and preferred models
        for cand in candidates:
            chosen = is_available(cand)
            if chosen:
                return _genai.GenerativeModel(chosen), chosen

        # Fallback: pick first model that supports generateContent
        if available_gc:
            chosen = sorted(available_gc)[0]
            return _genai.GenerativeModel(chosen), chosen

    except Exception as e:
        print(f"[gemini] Fehler beim Listen/Wählen der Modelle: {e}")

    return None, None


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Try to parse JSON from LLM output, even if wrapped in Markdown or prose.

    Strategy:
    - First, try plain json.loads.
    - If that fails, try to find the first {...} block via regex and parse that.
    - As a last fallback, use ast.literal_eval on that block.
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find a JSON-like object in the text
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return ast.literal_eval(m.group(0))
        except Exception:
            return None


async def run_gemini(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Run a prompt against Gemini (async).

    Returns:
        Parsed JSON (dict) if the model responds with JSON (or JSON-like) text,
        otherwise None.
    """
    model, _ = build_gemini()
    if not model:
        return None
    try:
        resp = await model.generate_content_async(prompt)  # type: ignore
        text = getattr(resp, "text", None)
        if not text:
            return None
        return _parse_llm_json(text)
    except Exception as e:
        print(f"[gemini] Fehler: {e}")
        return None


# ======================= DuckDuckGo Search (ddgs) =======================

_DDGS_AVAILABLE = False
try:
    # `ddgs` is used for DuckDuckGo (unofficial) text search.
    import ddgs  # type: ignore
    _DDGS_AVAILABLE = True
except Exception:
    _DDGS_AVAILABLE = False


# =============================== FastAPI =====================================

app = FastAPI(title="Colours of Wine API", version="0.9.0")

# Allow any origin for now – this can be restricted for production deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================== Pydantic Models ==============================


class AnalyzeRequest(BaseModel):
    """
    Input payload for /analyze.

    Attributes:
        wine_name: Arbitrary user-provided wine description (e.g. "Riesling Bürklin-Wolf 2021").
        use_llm: If True, Gemini will be used to fill missing fields and create viz profile.
    """
    wine_name: str = Field(..., description='z. B. "Riesling Bürklin-Wolf 2021"')
    use_llm: Optional[bool] = Field(
        default=None,
        description="Aktiviere LLM-Anreicherung (nur fehlende Felder)",
    )


class SourceItem(BaseModel):
    """
    Single search result item from DuckDuckGo.

    Attributes:
        title: Result title.
        url: Result URL.
        snippet: Short text snippet/description.
        score: Heuristic relevance score (higher is better).
    """
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None  # Relevanzscore


class ColorInfo(BaseModel):
    """
    Simple color descriptor used as legacy / fallback color model.

    Attributes:
        name: Human-readable color name (e.g. "pale straw").
        hex: Hex color string (e.g. "#F6F2AF").
        rgb: RGB triple.
    """
    name: str
    hex: str
    rgb: Tuple[int, int, int]


class WineProps(BaseModel):
    """
    Structured wine properties as used by the app and returned to the frontend.
    """
    vintage: Optional[int] = None
    wine_type: Optional[str] = None  # e.g. "red", "white", "rosé"
    variety: Optional[str] = None  # e.g. "Riesling"
    grapes: List[str] = []
    country: Optional[str] = None
    region: Optional[str] = None
    appellation: Optional[str] = None
    producer: Optional[str] = None
    style: Optional[str] = None  # "still", "sparkling", "fortified"
    sweetness: Optional[str] = None  # "dry", "off-dry", "medium-sweet", "sweet"
    alcohol: Optional[float] = None  # ABV in %
    oak: Optional[bool] = None
    tasting_notes: List[str] = []  # e.g. ["apple", "mineral", "citrus"]


class VizProfile(BaseModel):
    """
    Visualization profile for the frontend (aroma wheel, radar, etc.).

    All numeric fields are normalized to [0, 1] via clamp().
    """
    base_color_hex: Optional[str] = None
    acidity: float = 0.4
    body: float = 0.4
    tannin: float = 0.2
    depth: float = 0.4
    sweetness: float = 0.1
    oak: float = 0.1
    bubbles: bool = False
    fruit: List[str] = []
    non_fruit: List[str] = []
    mineral: float = 0.2
    ripe_aromas: float = 0.2

    def clamp(self) -> None:
        """
        Clamp all numeric attributes to the range [0.0, 1.0].
        """

        def c(v: float) -> float:
            return max(0.0, min(1.0, float(v)))

        self.acidity = c(self.acidity)
        self.body = c(self.body)
        self.tannin = c(self.tannin)
        self.depth = c(self.depth)
        self.sweetness = c(self.sweetness)
        self.oak = c(self.oak)
        self.mineral = c(self.mineral)
        self.ripe_aromas = c(self.ripe_aromas)


class AnalyzeResponse(BaseModel):
    """
    Main response model for /analyze.

    Includes:
      - original wine name,
      - search meta-data,
      - properties,
      - visualization profile,
      - legacy color fields for older FE code.
    """
    wine_name: str
    searched_query: str
    engine: str
    tried_queries: List[str] = []
    found: bool
    props: WineProps
    sources: List[SourceItem] = []
    notes: List[str] = []
    used_llm: bool = False
    reasoning: Optional[str] = None
    viz: Optional[VizProfile] = None
    # Legacy for frontend compatibility
    color: Optional[ColorInfo] = None
    hex: Optional[str] = None
    rgb: Optional[List[int]] = None
    note: Optional[str] = None


# ============================== Heuristics / Constants =======================

# DDG safesearch mode (e.g. "moderate", "strict", "off")
DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

# Very small built-in color lookup table (used as fallback/legacy)
COLOR_TABLE: Dict[str, str] = {
    "pale straw": "#F6F2AF",
    "rosé": "#F4A6B0",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
}

def _rgb_from_hex(h: str) -> Tuple[int, int, int]:
    """
    Convert a hex color string '#RRGGBB' into an (R, G, B) tuple.
    """
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def pick_color_heuristic(text: str) -> ColorInfo:
    """
    Crude heuristic to pick a base color given the wine name/description.

    Rules:
      - Riesling / Grüner / Sauvignon / Pinot Grigio / similar => pale straw.
      - rosé keywords => rosé.
      - Nebbiolo / Sangiovese / Chianti => garnet.
      - everything else => ruby.
    """
    t = text.lower()
    if any(k in t for k in ["riesling", "grüner", "sauvignon", "pinot grigio", "albari", "vermentino"]):
        name = "pale straw"
    elif "rosé" in t or "rose" in t:
        name = "rosé"
    elif any(k in t for k in ["nebbiolo", "sangiovese", "chianti"]):
        name = "garnet"
    else:
        name = "ruby"
    hx = COLOR_TABLE[name]
    return ColorInfo(name=name, hex=hx, rgb=_rgb_from_hex(hx))


# ------------------------------ Search Helpers -------------------------------

# Preferred domains for wine-specific websites (boosts ranking)
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
    "weingut",  # substring match
    "winery",   # substring match
]

def _domain_priority(url: str) -> int:
    """
    Assign a priority score based on the presence of preferred domains.

    Returns:
        Higher integer for higher priority, 0 for unknown domains.
    """
    for i, d in enumerate(PREFERRED_DOMAINS):
        if d in (url or ""):
            # Reverse scoring: first entries in PREFERRED_DOMAINS get highest score.
            return len(PREFERRED_DOMAINS) - i
    return 0

def _normalize_name(name: str) -> Tuple[str, str, Optional[str]]:
    """
    Normalize a wine name and extract vintage year if present.

    Args:
        name: User-provided wine name.

    Returns:
        (full_name, base_without_vintage, vintage_year_str_or_None)
    """
    # Normalize whitespace
    name = re.sub(r"\s+", " ", name).strip()

    # Match vintage in a reasonably realistic range (1960–2049)
    m = re.search(r"\b(19[6-9]\d|20[0-4]\d)\b", name)
    vintage = m.group(1) if m else None
    base = name
    if vintage:
        # Remove vintage string from base name
        base = re.sub(re.escape(vintage), "", name).strip()

    # Remove generic "wine"/"wein" words from base
    base = re.sub(r"\b(wein|wine)\b", "", base, flags=re.I).strip()
    return name, base, vintage

async def _ddg_text(query: str, region: str, max_results: int = 12) -> List[SourceItem]:
    """
    Perform a text search using ddgs and return a list of SourceItem.

    Args:
        query: Search query.
        region: DuckDuckGo region string, e.g. "de-de", "us-en".
        max_results: Max number of search results to request.

    Returns:
        List of SourceItem; may be empty if ddgs not installed or error occurs.
    """
    if not _DDGS_AVAILABLE:
        print("[ddg] ddgs nicht installiert -> keine Quellen.")
        return []
    from ddgs import DDGS  # type: ignore

    res: List[SourceItem] = []
    try:
        with DDGS() as ddg:
            print(f"[ddg] {region} :: {query}")
            for r in ddg.text(query, region=region, safesearch=DDG_SAFE, max_results=max_results):
                title = r.get("title")
                url = r.get("href") or r.get("url")
                snippet = r.get("body")
                if url and title:
                    res.append(SourceItem(title=title, url=url, snippet=snippet))
    except Exception as e:
        print(f"[ddg] Fehler ({region}): {e}")
    return res


def _dedup_sources(items: List[SourceItem]) -> List[SourceItem]:
    """
    Remove duplicate URLs (ignoring query parameters) from search results.
    """
    seen = set()
    out: List[SourceItem] = []
    for s in items:
        key = (s.url or "").split("?")[0]
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out

def _score_source(s: SourceItem, base: str, vintage: Optional[str]) -> float:
    """
    Score a SourceItem based on text overlap with the base wine name, vintage,
    and domain priority.
    """
    t = f"{s.title or ''} {s.snippet or ''}".lower()
    base_l = base.lower()
    score = 0.0

    # Full base string match
    if base_l and base_l in t:
        score += 5.0
    # token overlap
    tokens = [w for w in re.split(r"[^\wäöüÄÖÜß]+", base_l) if w]
    score += sum(0.8 for w in tokens if w in t)

    # Vintage match
    if vintage and vintage in t:
        score += 1.5

    # Domain priority
    score += 0.3 * _domain_priority(s.url or "")
    return score

def _rank_and_filter(items: List[SourceItem], wine_name: str) -> List[SourceItem]:
    """
    Filter and rank source items for relevance to the given wine name.

    Filter rule:
        Keep only those items that contain at least one token from base name
        or the vintage year.

    Returns:
        Top ~10 ranked SourceItem.
    """
    full, base, vintage = _normalize_name(wine_name)

    filtered: List[SourceItem] = []
    for s in items:
        txt = f"{s.title or ''} {s.snippet or ''}".lower()
        # check for at least one matching token or vintage
        if any(w for w in base.lower().split() if w and w in txt) or (vintage and vintage in txt):
            s.score = _score_source(s, base, vintage)
            filtered.append(s)
    filtered.sort(key=lambda x: x.score or 0.0, reverse=True)
    return filtered[:10]


# -------------- Property Extraction (Heuristics) ----------------

# Basic country list for heuristics
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
VARIETIES = [
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

# (keyword, normalized sweetness)
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


def _first_match(pat: str, text: str, flags=re.I) -> Optional[str]:
    """
    Return the first capturing group of the first regex match or None.
    """
    m = re.search(pat, text, flags)
    return m.group(1) if m else None


def extract_props(wine_name: str, sources: List[SourceItem]) -> WineProps:
    """
    Extract WineProps from wine name and search sources using regex heuristics.

    This is the main non-LLM extraction mechanism. It tries to infer:
      - vintage, producer, country, region, variety, style, sweetness, ABV, oak, tasting notes.
    """
    # Combine all text into a single blob (name + titles + snippets)
    blob_parts = [wine_name] + [s.title or "" for s in sources] + [s.snippet or "" for s in sources]
    blob = "\n".join(blob_parts)
    props = WineProps()

    # Vintage (1960–2049)
    vin = _first_match(r"\b(19[6-9]\d|20[0-4]\d)\b", blob)
    if vin:
        props.vintage = int(vin)

    # Producer (heuristic: "Weingut X" or "Lastname Lastname" followed by a recognizable variety)
    prod = _first_match(
        r"(Weingut\s+[A-ZÄÖÜ][\w\-\s]+?|[A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+){0,3})\s+("
        r"Riesling|Chardonnay|Pinot|Sauvignon|Grüner|Blaufränkisch|Zweigelt|Sangiovese|"
        r"Nebbiolo|Merlot|Cabernet)",
        blob,
    )
    if prod:
        props.producer = prod.strip()

    # Country
    for c in COUNTRIES:
        if re.search(r"\b" + re.escape(c) + r"\b", blob, re.I):
            props.country = c
            break

    # Region (small list of common examples)
    reg = _first_match(
        r"\b(Pfalz|Mosel|Wachau|Kamptal|Ahr|Nahe|Rheingau|Tuscany|Burgundy|Bordeaux|Rioja|Mendoza)\b",
        blob,
    )
    if reg:
        props.region = reg

    # Variety & wine type
    for v, typ in VARIETIES:
        if re.search(r"\b" + re.escape(v) + r"\b", blob, re.I):
            props.variety = v
            props.wine_type = {"white": "white", "red": "red"}[typ]
            props.grapes = [v]
            break

    # Rosé fallback if no explicit variety-based type
    if not props.wine_type and re.search(r"\bros[ée]\b", blob, re.I):
        props.wine_type = "rosé"

    # Style: sparkling / fortified / still
    props.style = (
        "sparkling"
        if any(re.search(r"\b" + w + r"\b", blob, re.I) for w in SPARK_WORDS)
        else "still"
    )
    if re.search(r"\b(port|sherry|madeira)\b", blob, re.I):
        props.style = "fortified"

    # Sweetness
    for de, en in SWEET_WORDS:
        if re.search(r"\b" + de + r"\b", blob, re.I):
            props.sweetness = en
            break

    # ABV / alcohol content (robust to different languages and formats)
    alc = (
            _first_match(r"(\d{1,2}(?:[.,]\d)?)\s*%\s*(?:vol|abv)\b", blob)
            or _first_match(r"(?:alkohol|alc\.?|alcohol)\s*[:=]??\s*(\d{1,2}(?:[.,]\d)?)\s*%", blob)
            or _first_match(r"(\d{1,2}(?:[.,]\d)?)\s*%", blob)
    )
    if alc:
        try:
            props.alcohol = float(alc.replace(",", "."))
        except Exception:
            pass

    # Oak / barrel usage
    if any(re.search(r"\b" + w + r"\b", blob, re.I) for w in OAK_WORDS):
        props.oak = True

    # Tasting notes (very small controlled vocab)
    tn = re.findall(
        r"\b(apple|pear|peach|citrus|lemon|lime|apricot|pineapple|herb|spice|vanilla|cherry|"
        r"raspberry|strawberry|plum|pepper|smoke|mineral)\b",
        blob,
        re.I,
    )
    if tn:
        props.tasting_notes = sorted(set([t.lower() for t in tn]))
    return props


# ------------------------- LLM Prompt Builders -------------------------------


def _build_llm_prompt_struct(wine_name: str, snippets: List[SourceItem]) -> str:
    """
    Build a structured prompt for Gemini when we already have search snippets.

    The prompt:
      - Specifies the exact JSON format to return.
      - Provides multiple source snippets as context.
      - Asks the model to provide typical values if exact ones are missing.
    """
    lines = [
        "Extrahiere Eigenschaften UND ein Visualisierungsprofil als kompaktes JSON.",
        "Wenn exakte Angaben fehlen (z.B. Alkohol %), gib einen **typischen** Wert für diesen Weintyp/Jahrgang an.",
        "Gib **nur** JSON zurück mit Feldern:",
        '{'
        '"props":{"vintage":int|null,"wine_type":"red|white|rosé|sparkling"|null,'
        '"variety":str|null,"grapes":[str],"country":str|null,"region":str|null,'
        '"appellation":str|null,"producer":str|null,"style":str|null,"sweetness":str|null,'
        '"alcohol":float|null,"oak":bool|null,"tasting_notes":[str]},'
        '"viz":{"base_color_hex":str|null,"acidity":float,"body":float,"tannin":float,'
        '"depth":float,"sweetness":float,"oak":float,"bubbles":bool,"fruit":[str],'
        '"non_fruit":[str],"mineral":float,"ripe_aromas":float}'
        '}',
        f'Wein: "{wine_name}"',
        "Snippets (nur zur Ableitung):",
    ]
    for s in snippets[:6]:
        lines.append(f"- {s.title or ''} — {s.snippet or ''}")
    return "\n".join(lines)


def _build_llm_prompt_from_name(wine_name: str) -> str:
    """
    Build a fallback prompt when we have no search snippets at all.

    Here the model must rely on typical properties for the given wine name.
    """
    return (
        "Leite typische Eigenschaften und ein Visualisierungsprofil ab. "
        "Wenn exakte Angaben fehlen (z.B. Alkohol %), nutze plausible Standardwerte. "
        "Antworte **nur** als JSON mit Feldern 'props' und 'viz' wie oben. "
        f'Wein: "{wine_name}"'
    )

# =============================== Health ======================================

@app.get("/health")
def health():
    model, chosen = build_gemini()
    return {
        "status": "ok",
        "llm_available": bool(model),
        "gemini_model": chosen,
        "api_key_set": GEMINI_KEY_SET,
        "ddg_available": _DDGS_AVAILABLE,
    }

# ============================ Merge (nicht destruktiv) =======================

def _merge_props_non_destructive(base: WineProps, llm_props: Dict[str, Any]) -> WineProps:
    """
    Merge LLM-generated props into existing WineProps in a non-destructive way.

    Rules:
      - Existing non-empty values in `base` are never overwritten.
      - For list fields (grapes, tasting_notes), values are unioned and deduplicated.
      - For numeric/bool fields:
          only set if current value is None and LLM has a non-None.
      - For strings:
          only set if current value is missing/empty and LLM has a non-empty value.
    """
    merged = base.model_dump()

    def is_missing(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, list):
            return len(v) == 0
        return False

    for k, v in llm_props.items():
        if k in ("grapes", "tasting_notes"):
            # Merge lists by unioning stringified entries
            base_list = merged.get(k) or []
            if isinstance(v, list):
                merged[k] = sorted({*(str(x) for x in base_list), *(str(x) for x in v)})
            else:
                merged[k] = base_list
            continue

        cur = merged.get(k, None)

        # Numeric/bool or None: only set if currently None
        if cur is None and v is not None:
            merged[k] = v
            continue

        # Strings / others: set only if current is missing/empty
        if is_missing(cur) and v not in (None, "", []):
            merged[k] = v

    return WineProps(**merged)

# ============================== Analyze ======================================

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Main API endpoint: analyze a wine name.

    Steps:
      1. Normalize wine name, extract vintage.
      2. Run several targeted DuckDuckGo searches in two regions (de-de, us-en).
      3. Deduplicate + rank results; keep top sources.
      4. Extract WineProps via regex heuristics from all text.
      5. If requested, call Gemini to fill missing props and create VizProfile.
      6. Pick a base color via heuristic and, if needed, fill viz.base_color_hex.
      7. Return all information as AnalyzeResponse.
    """
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    full, base, vintage = _normalize_name(wine)

    # DDG search – several focused queries, across regions
    tried: List[str] = []
    regions = ["de-de", "us-en"]
    queries = [
        f'"{full}"',
        f'"{base}" {vintage or ""} site:vivino.com OR site:winesearcher.com OR site:wine.com',
        f'{base} {vintage or ""} site:wikipedia.org OR site:falstaff.com OR site:wein.plus',
        f"{full} wine",
        full,
    ]

    sources: List[SourceItem] = []
    used_query = queries[0]
    used_engine = "ddg:de-de"

    raw: List[SourceItem] = []
    for q in queries:
        for reg in regions:
            tried.append(f"{reg} :: {q}")
            res = await _ddg_text(q, reg, max_results=12)
            if res:
                raw.extend(res)
        # Stop at first query that yields any results
        if raw:
            break

    # Deduplicate + rank
    if raw:
        raw = _dedup_sources(raw)
        ranked = _rank_and_filter(raw, wine)
        sources = ranked
        used_query = queries[0]
        used_engine = "ddg+rank"
    else:
        sources = []
        used_engine = "ddg:none"

    notes: List[str] = []
    if not sources:
        notes.append("Keine passenden Weintreffer – Analyse basiert auf Heuristik.")

    # Baseline heuristic properties from name + search snippets
    props = extract_props(wine, sources)

    used_llm = False
    reasoning: Optional[str] = None
    viz_profile: Optional[VizProfile] = None

    # Use LLM only if requested by the client.
    if req.use_llm:
        llm_json = await run_gemini(
            _build_llm_prompt_struct(wine, sources)
            if sources
            else _build_llm_prompt_from_name(wine)
        )
        if llm_json:
            try:
                llm_props = llm_json.get("props") or {}
                llm_viz = llm_json.get("viz") or {}

                # Non-destructive merge of props (heuristics stay authoritative)
                props = _merge_props_non_destructive(props, llm_props)

                # Viz profile comes primarily from LLM (and will be clamped)
                vp = VizProfile(**llm_viz)
                vp.clamp()
                viz_profile = vp

                used_llm = True
                reasoning = (
                    "LLM hat fehlende Felder ergänzt (inkl. plausibler ABV-Schätzung) – "
                    "nichts überschrieben."
                )
            except Exception as e:
                notes.append(f"LLM-Parsing-Fehler: {e}")
        else:
            notes.append("LLM nicht verfügbar oder unbrauchbare Antwort – es bleibt bei Heuristik.")

    # Farbe (Legacy / Fallback)
    color = pick_color_heuristic(wine)

    # If LLM didn't specify a base color, fill it with the heuristic one.
    if viz_profile and not viz_profile.base_color_hex:
        viz_profile.base_color_hex = color.hex

    legacy_note = (
        "LLM ergänzt fehlende Daten"
        if used_llm
        else (notes[0] if notes else "Heuristik/Regeln")
    )

    return AnalyzeResponse(
        wine_name=wine,
        searched_query=used_query,
        engine=used_engine,
        tried_queries=tried,
        found=len(sources) > 0,
        props=props,
        sources=sources,
        notes=notes,
        used_llm=used_llm,
        reasoning=reasoning,
        viz=viz_profile,
        color=color,
        hex=color.hex,
        rgb=[*color.rgb],
        note=legacy_note,
    )

# backend/app.py
from __future__ import annotations

import os
import re
import json
import ast
from typing import List, Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ======================= Gemini (Google Generative AI) =======================

GEMINI_MODEL_ENV = os.getenv("GEMINI_MODEL", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_KEY_SET = bool(GOOGLE_API_KEY)

PREFERRED_MODELS = [
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-8b-latest",
]

_genai = None
try:
    import google.generativeai as genai  # type: ignore
    _genai = genai
    if GEMINI_KEY_SET:
        _genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    _genai = None


def build_gemini():
    if not (_genai and GEMINI_KEY_SET):
        return None, None

    try:
        available = list(_genai.list_models())
        available_gc = {
            m.name
            for m in available
            if hasattr(m, "supported_generation_methods")
               and "generateContent" in getattr(m, "supported_generation_methods", [])
        }

        candidates: List[str] = []
        if GEMINI_MODEL_ENV:
            candidates.append(GEMINI_MODEL_ENV)
        candidates.extend([m for m in PREFERRED_MODELS if m != GEMINI_MODEL_ENV])

        def is_available(name: str) -> Optional[str]:
            if name in available_gc:
                return name
            short = f"models/{name}"
            if short in available_gc:
                return short
            return None

        for cand in candidates:
            chosen = is_available(cand)
            if chosen:
                return _genai.GenerativeModel(chosen), chosen

        if available_gc:
            chosen = sorted(available_gc)[0]
            return _genai.GenerativeModel(chosen), chosen

    except Exception as e:
        print(f"[gemini] Fehler beim Listen/Wählen der Modelle: {e}")

    return None, None


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """Versucht JSON auch dann zu parsen, wenn das Model Markdown o.ä. zurückgibt."""
    try:
        return json.loads(text)
    except Exception:
        pass
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
    import ddgs  # type: ignore
    _DDGS_AVAILABLE = True
except Exception:
    _DDGS_AVAILABLE = False


# =============================== FastAPI =====================================

app = FastAPI(title="Colours of Wine API", version="0.9.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================== Models =======================================

class AnalyzeRequest(BaseModel):
    wine_name: str = Field(..., description='z. B. "Riesling Bürklin-Wolf 2021"')
    use_llm: Optional[bool] = Field(default=None, description="Aktiviere LLM-Anreicherung (nur fehlende Felder)")


class SourceItem(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None  # Relevanzscore


class ColorInfo(BaseModel):
    name: str
    hex: str
    rgb: Tuple[int, int, int]


class WineProps(BaseModel):
    vintage: Optional[int] = None
    wine_type: Optional[str] = None
    variety: Optional[str] = None
    grapes: List[str] = []
    country: Optional[str] = None
    region: Optional[str] = None
    appellation: Optional[str] = None
    producer: Optional[str] = None
    style: Optional[str] = None
    sweetness: Optional[str] = None
    alcohol: Optional[float] = None
    oak: Optional[bool] = None
    tasting_notes: List[str] = []


class VizProfile(BaseModel):
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

    def clamp(self):
        def c(v): return max(0.0, min(1.0, float(v)))
        self.acidity = c(self.acidity)
        self.body = c(self.body)
        self.tannin = c(self.tannin)
        self.depth = c(self.depth)
        self.sweetness = c(self.sweetness)
        self.oak = c(self.oak)
        self.mineral = c(self.mineral)
        self.ripe_aromas = c(self.ripe_aromas)


class AnalyzeResponse(BaseModel):
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
    # Legacy fürs Frontend
    color: Optional[ColorInfo] = None
    hex: Optional[str] = None
    rgb: Optional[List[int]] = None
    note: Optional[str] = None


# ============================== Heuristiken ==================================

DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

COLOR_TABLE = {
    "pale straw": "#F6F2AF",
    "rosé": "#F4A6B0",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
}

def _rgb_from_hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def pick_color_heuristic(text: str) -> ColorInfo:
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


# ------------------------------ Suche ----------------------------------------

# Bevorzugte Domains für Wein-spezifische Seiten
PREFERRED_DOMAINS = [
    "vivino.com", "wine.com", "winesearcher.com", "cellartracker.com",
    "wein.plus", "falstaff.com", "weinfeder.de", "winelibrary.com",
    "wikipedia.org", "weingueter.de", "weingut", "winery",
]

def _domain_priority(url: str) -> int:
    for i, d in enumerate(PREFERRED_DOMAINS):
        if d in (url or ""):
            return len(PREFERRED_DOMAINS) - i
    return 0

def _normalize_name(name: str) -> Tuple[str, str, Optional[str]]:
    """Gibt (voll, ohne Jahrgang, jahrgang) zurück."""
    name = re.sub(r"\s+", " ", name).strip()
    m = re.search(r"\b(19[6-9]\d|20[0-4]\d)\b", name)
    vintage = m.group(1) if m else None
    base = name
    if vintage:
        base = re.sub(re.escape(vintage), "", name).strip()
    # unnötige Schlüsselwörter entfernen
    base = re.sub(r"\b(wein|wine)\b", "", base, flags=re.I).strip()
    return name, base, vintage

async def _ddg_text(query: str, region: str, max_results: int = 12) -> List[SourceItem]:
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
    seen = set()
    out: List[SourceItem] = []
    for s in items:
        key = (s.url or "").split("?")[0]
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out

def _score_source(s: SourceItem, base: str, vintage: Optional[str]) -> float:
    t = f"{s.title or ''} {s.snippet or ''}".lower()
    base_l = base.lower()
    score = 0.0
    if base_l and base_l in t:
        score += 5.0
    # token overlap
    tokens = [w for w in re.split(r"[^\wäöüÄÖÜß]+", base_l) if w]
    score += sum(0.8 for w in tokens if w in t)
    if vintage and vintage in t:
        score += 1.5
    score += 0.3 * _domain_priority(s.url or "")
    return score

def _rank_and_filter(items: List[SourceItem], wine_name: str) -> List[SourceItem]:
    full, base, vintage = _normalize_name(wine_name)
    # Filter: mindestens Produzent/Sortenwort oder Vintage enthalten
    filtered = []
    for s in items:
        txt = f"{s.title or ''} {s.snippet or ''}".lower()
        if any(w for w in base.lower().split() if w and w in txt) or (vintage and vintage in txt):
            s.score = _score_source(s, base, vintage)
            filtered.append(s)
    filtered.sort(key=lambda x: x.score or 0.0, reverse=True)
    return filtered[:10]

# -------------- Property Extraction (Heuristik) ----------------

COUNTRIES = [
    "Austria","Germany","France","Italy","Spain","Portugal","USA","Australia",
    "New Zealand","South Africa","Chile","Argentina",
]
VARIETIES = [
    ("Riesling","white"),("Grüner Veltliner","white"),("Sauvignon Blanc","white"),
    ("Chardonnay","white"),("Pinot Grigio","white"),("Gewürztraminer","white"),
    ("Pinot Noir","red"),("Sangiovese","red"),("Nebbiolo","red"),
    ("Cabernet Sauvignon","red"),("Merlot","red"),("Syrah","red"),
    ("Zweigelt","red"),("Blaufränkisch","red"),("St. Laurent","red"),
]
SWEET_WORDS = [
    ("trocken","dry"),("dry","dry"),("halbtrocken","off-dry"),("off-dry","off-dry"),
    ("lieblich","medium-sweet"),("semi-sweet","medium-sweet"),("süß","sweet"),("sweet","sweet"),
]
SPARK_WORDS = ["sparkling","sekt","champagne","cava","prosecco","spumante","frizzante"]
OAK_WORDS = ["oak","barrique","oak-aged","holzfass","eiche","eichenfass"]


def _first_match(pat: str, text: str, flags=re.I) -> Optional[str]:
    m = re.search(pat, text, flags)
    return m.group(1) if m else None


def extract_props(wine_name: str, sources: List[SourceItem]) -> WineProps:
    blob_parts = [wine_name] + [s.title or "" for s in sources] + [s.snippet or "" for s in sources]
    blob = "\n".join(blob_parts)
    props = WineProps()

    vin = _first_match(r"\b(19[6-9]\d|20[0-4]\d)\b", blob)
    if vin:
        props.vintage = int(vin)

    prod = _first_match(
        r"(Weingut\s+[A-ZÄÖÜ][\w\-\s]+?|[A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+){0,3})\s+("
        r"Riesling|Chardonnay|Pinot|Sauvignon|Grüner|Blaufränkisch|Zweigelt|Sangiovese|"
        r"Nebbiolo|Merlot|Cabernet)",
        blob,
    )
    if prod:
        props.producer = prod.strip()

    for c in COUNTRIES:
        if re.search(r"\b" + re.escape(c) + r"\b", blob, re.I):
            props.country = c
            break
    reg = _first_match(
        r"\b(Pfalz|Mosel|Wachau|Kamptal|Ahr|Nahe|Rheingau|Tuscany|Burgundy|Bordeaux|Rioja|Mendoza)\b",
        blob,
    )
    if reg:
        props.region = reg

    for v, typ in VARIETIES:
        if re.search(r"\b" + re.escape(v) + r"\b", blob, re.I):
            props.variety = v
            props.wine_type = {"white": "white", "red": "red"}[typ]
            props.grapes = [v]
            break
    if not props.wine_type and re.search(r"\bros[ée]\b", blob, re.I):
        props.wine_type = "rosé"

    props.style = "sparkling" if any(re.search(r"\b" + w + r"\b", blob, re.I) for w in SPARK_WORDS) else "still"
    if re.search(r"\b(port|sherry|madeira)\b", blob, re.I):
        props.style = "fortified"

    for de, en in SWEET_WORDS:
        if re.search(r"\b" + de + r"\b", blob, re.I):
            props.sweetness = en
            break

    # ABV/Alkohol (robust in mehreren Sprachen)
    alc = _first_match(r"(\d{1,2}(?:[.,]\d)?)\s*%\s*(?:vol|abv)\b", blob) \
          or _first_match(r"(?:alkohol|alc\.?|alcohol)\s*[:=]??\s*(\d{1,2}(?:[.,]\d)?)\s*%", blob) \
          or _first_match(r"(\d{1,2}(?:[.,]\d)?)\s*%", blob)
    if alc:
        try:
            props.alcohol = float(alc.replace(",", "."))
        except Exception:
            pass

    if any(re.search(r"\b" + w + r"\b", blob, re.I) for w in OAK_WORDS):
        props.oak = True

    tn = re.findall(
        r"\b(apple|pear|peach|citrus|lemon|lime|apricot|pineapple|herb|spice|vanilla|cherry|"
        r"raspberry|strawberry|plum|pepper|smoke|mineral)\b",
        blob,
        re.I,
    )
    if tn:
        props.tasting_notes = sorted(set([t.lower() for t in tn]))
    return props


# ------------------------- LLM Prompts -------------------------

def _build_llm_prompt_struct(wine_name: str, snippets: List[SourceItem]) -> str:
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
        "Snippets (nur zur Ableitung):"
    ]
    for s in snippets[:6]:
        lines.append(f"- {s.title or ''} — {s.snippet or ''}")
    return "\n".join(lines)


def _build_llm_prompt_from_name(wine_name: str) -> str:
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
    """Ergänzt nur fehlende Felder. Listen werden vereinigt, nichts überschrieben."""
    merged = base.model_dump()

    def is_missing(v):
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, list):
            return len(v) == 0
        return False

    for k, v in llm_props.items():
        if k in ("grapes", "tasting_notes"):
            base_list = merged.get(k) or []
            if isinstance(v, list):
                merged[k] = sorted({*(str(x) for x in base_list), *(str(x) for x in v)})
            else:
                merged[k] = base_list
            continue

        cur = merged.get(k, None)
        # numerisch/bool oder None: nur setzen, wenn aktuell nicht belegt
        if cur is None and v is not None:
            merged[k] = v
            continue

        # strings/sonstiges: nur wenn leer/fehlend
        if is_missing(cur) and v not in (None, "", []):
            merged[k] = v

    return WineProps(**merged)

# ============================== Analyze ======================================

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    full, base, vintage = _normalize_name(wine)

    # DDG-Suche – mehrere, gezielt fokussierte Queries
    tried: List[str] = []
    regions = ["de-de", "us-en"]
    queries = [
        f'"{full}"',
        f'"{base}" {vintage or ""} site:vivino.com OR site:winesearcher.com OR site:wine.com',
        f'{base} {vintage or ""} site:wikipedia.org OR site:falstaff.com OR site:wein.plus',
        f'{full} wine',
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
        if raw:
            break

    # Deduplizieren, dann ranken
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

    # Heuristische Grundeigenschaften
    props = extract_props(wine, sources)

    used_llm = False
    reasoning = None
    viz_profile: Optional[VizProfile] = None

    # LLM NUR, wenn der Client das explizit anfordert
    if req.use_llm:
        llm_json = await run_gemini(
            _build_llm_prompt_struct(wine, sources) if sources else _build_llm_prompt_from_name(wine)
        )
        if llm_json:
            try:
                llm_props = llm_json.get("props") or {}
                llm_viz = llm_json.get("viz") or {}

                # *** NICHT DESTRUKTIVES MERGEN ***
                props = _merge_props_non_destructive(props, llm_props)

                # viz kommt typischerweise nur vom LLM – kein Überschreiben von Props
                vp = VizProfile(**llm_viz)
                vp.clamp()
                viz_profile = vp

                used_llm = True
                reasoning = "LLM hat fehlende Felder ergänzt (inkl. plausibler ABV-Schätzung) – nichts überschrieben."
            except Exception as e:
                notes.append(f"LLM-Parsing-Fehler: {e}")
        else:
            notes.append("LLM nicht verfügbar oder unbrauchbare Antwort – es bleibt bei Heuristik.")

    # Farbe (Legacy / Fallback)
    color = pick_color_heuristic(wine)
    if viz_profile and not viz_profile.base_color_hex:
        viz_profile.base_color_hex = color.hex

    legacy_note = (
        "LLM ergänzt fehlende Daten" if used_llm else (notes[0] if notes else "Heuristik/Regeln")
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

# backend/app.py
from __future__ import annotations
import os, re, json, ast
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------- (optional) Gemini ----------
_GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai  # type: ignore
    if os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_AVAILABLE = False

app = FastAPI(title="Colours of Wine API", version="0.3.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

class AnalyzeRequest(BaseModel):
    wine_name: str = Field(..., description='z. B. "Riesling Bürklin-Wolf 2021"')

class SourceItem(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None

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
    # legacy für Frontend (wird dort nur für die Visualisierung genutzt)
    color: Optional[ColorInfo] = None
    hex: Optional[str] = None
    rgb: Optional[List[int]] = None
    note: Optional[str] = None

DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

COLOR_TABLE = {
    "pale straw": "#F6F2AF",
    "rosé": "#F4A6B0",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
}
def _rgb_from_hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

def pick_color_heuristic(text: str) -> ColorInfo:
    t = text.lower()
    if any(k in t for k in ["riesling","grüner","sauvignon","pinot grigio","albari","vermentino"]):
        name = "pale straw"
    elif "rosé" in t or "rose" in t:
        name = "rosé"
    elif any(k in t for k in ["nebbiolo","sangiovese","chianti"]):
        name = "garnet"
    else:
        name = "ruby"
    hx = COLOR_TABLE[name]
    return ColorInfo(name=name, hex=hx, rgb=_rgb_from_hex(hx))

# ---------------- DuckDuckGo Helper ----------------
async def _ddg_text(query: str, region: str, max_results: int = 8) -> List[SourceItem]:
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        print("[ddg] ddgs nicht installiert -> keine Quellen.")
        return []
    res: List[SourceItem] = []
    try:
        with DDGS() as ddgs:
            print(f"[ddg] {region} :: {query}")
            for r in ddgs.text(query, region=region, safesearch=DDG_SAFE, max_results=max_results):
                title = r.get("title")
                url = r.get("href") or r.get("url")
                snippet = r.get("body")
                if url and title:
                    res.append(SourceItem(title=title, url=url, snippet=snippet))
    except Exception as e:
        print(f"[ddg] Fehler ({region}): {e}")
    return res

def _dedup_sources(items: List[SourceItem]) -> List[SourceItem]:
    seen = set(); out: List[SourceItem] = []
    for s in items:
        key = (s.url or "").split("?")[0]
        if key and key not in seen:
            seen.add(key); out.append(s)
    return out

# -------------- Property Extraction ----------------
COUNTRIES = ["Austria","Germany","France","Italy","Spain","Portugal","USA","Australia","New Zealand","South Africa","Chile","Argentina"]
VARIETIES = [
    ("Riesling","white"),("Grüner Veltliner","white"),("Sauvignon Blanc","white"),
    ("Chardonnay","white"),("Pinot Grigio","white"),("Gewürztraminer","white"),
    ("Pinot Noir","red"),("Sangiovese","red"),("Nebbiolo","red"),
    ("Cabernet Sauvignon","red"),("Merlot","red"),("Syrah","red"),
    ("Zweigelt","red"),("Blaufränkisch","red"),("St. Laurent","red"),
]
SWEET_WORDS = [("trocken","dry"),("dry","dry"),("halbtrocken","off-dry"),("off-dry","off-dry"),
               ("lieblich","medium-sweet"),("semi-sweet","medium-sweet"),("süß","sweet"),("sweet","sweet")]
SPARK_WORDS = ["sparkling","sekt","champagne","cava","prosecco","spumante","frizzante"]
OAK_WORDS = ["oak","barrique","oak-aged","holzfass","eiche","eichenfass"]

def _first_match(pat: str, text: str, flags=re.I) -> Optional[str]:
    m = re.search(pat, text, flags); return m.group(1) if m else None

def extract_props(wine_name: str, sources: List[SourceItem]) -> WineProps:
    blob_parts = [wine_name] + [s.title or "" for s in sources] + [s.snippet or "" for s in sources]
    blob = "\n".join(blob_parts)
    props = WineProps()

    vin = _first_match(r"\b(19[6-9]\d|20[0-4]\d)\b", blob)
    if vin: props.vintage = int(vin)

    prod = _first_match(r"(Weingut\s+[A-ZÄÖÜ][\w\-\s]+?|[A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+){0,3})\s+(Riesling|Chardonnay|Pinot|Sauvignon|Grüner|Blaufränkisch|Zweigelt|Sangiovese|Nebbiolo|Merlot|Cabernet)", blob)
    if prod: props.producer = prod.strip()

    for c in COUNTRIES:
        if re.search(r"\b"+re.escape(c)+r"\b", blob, re.I): props.country=c; break
    reg = _first_match(r"\b(Pfalz|Mosel|Wachau|Kamptal|Ahr|Nahe|Rheingau|Tuscany|Burgundy|Bordeaux|Rioja|Mendoza)\b", blob)
    if reg: props.region = reg

    for v, typ in VARIETIES:
        if re.search(r"\b"+re.escape(v)+r"\b", blob, re.I):
            props.variety=v; props.wine_type={"white":"white","red":"red"}[typ]; props.grapes=[v]; break
    if not props.wine_type and re.search(r"\bros[ée]\b", blob, re.I): props.wine_type="rosé"

    props.style = "sparkling" if any(re.search(r"\b"+w+r"\b", blob, re.I) for w in SPARK_WORDS) else "still"
    if re.search(r"\b(port|sherry|madeira)\b", blob, re.I): props.style="fortified"

    for de,en in SWEET_WORDS:
        if re.search(r"\b"+de+r"\b", blob, re.I): props.sweetness=en; break

    alc = _first_match(r"(\d{1,2}[.,]\d)\s*%[ ]*vol", blob) or _first_match(r"(\d{1,2}[.,]\d)\s*%", blob)
    if alc:
        try: props.alcohol = float(alc.replace(",", "."))
        except: pass

    if any(re.search(r"\b"+w+r"\b", blob, re.I) for w in OAK_WORDS): props.oak=True

    tn = re.findall(r"\b(apple|pear|peach|citrus|lemon|lime|apricot|pineapple|herb|spice|vanilla|cherry|raspberry|strawberry|plum|pepper|smoke|mineral)\b", blob, re.I)
    if tn: props.tasting_notes = sorted(set([t.lower() for t in tn]))
    return props

def _build_llm_prompt(wine_name: str, snippets: List[SourceItem]) -> str:
    lines = [
        "Extrahiere strukturierte Weineigenschaften als JSON:",
        '{"vintage": int|null, "wine_type": "red|white|rosé|sparkling"|null, "variety": str|null, "grapes":[str], "country": str|null, "region": str|null, "appellation": str|null, "producer": str|null, "style": str|null, "sweetness": str|null, "alcohol": float|null, "oak": bool|null, "tasting_notes":[str]}',
        f"Wein: {wine_name}", "Snippets:"]
    for s in snippets: lines.append(f"- {s.title or ''} — {s.snippet or ''}")
    return "\n".join(lines)

def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    try: return json.loads(text)
    except: pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except:
        try: return ast.literal_eval(m.group(0))
        except: return None

async def run_gemini(prompt: str) -> Optional[Dict[str, Any]]:
    if not _GEMINI_AVAILABLE: return None
    try:
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))  # type: ignore
        resp = await model.generate_content_async(prompt)  # type: ignore
        if hasattr(resp, "text"):  # type: ignore
            return _parse_llm_json(resp.text)  # type: ignore
    except Exception as e:
        print(f"[gemini] Fehler: {e}")
    return None

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    wine = (req.wine_name or "").strip()
    if not wine: raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    # --- mehrstufige Suche ---
    tried: List[str] = []
    regions = ["de-de", "us-en"]
    query_candidates = [
        f'"{wine}" site:vivino.com OR site:wine.com OR site:wikipedia.org',
        f'"{wine}"',
        wine,
        f'{wine} wine',
    ]

    sources: List[SourceItem] = []
    used_query = query_candidates[0]
    used_engine = "ddg:de-de"

    for q in query_candidates:
        for reg in regions:
            tried.append(f"{reg} :: {q}")
            res = await _ddg_text(q, reg, max_results=8)
            if res:
                sources = _dedup_sources(res)
                used_query = q
                used_engine = f"ddg:{reg}"
                break
        if sources: break

    notes: List[str] = []
    if not sources:
        notes.append("Keine Treffer von DDG (probiert: " + "; ".join(tried) + ").")

    # Eigenschaften
    props = extract_props(wine, sources)

    # optional: LLM-Verfeinerung
    used_llm = False
    reasoning = None
    if _GEMINI_AVAILABLE and sources:
        llm = await run_gemini(_build_llm_prompt(wine, sources))
        if llm:
            try:
                merged = {**props.model_dump(), **llm}
                props = WineProps(**merged)
                used_llm = True
                reasoning = "(LLM verfeinert)"
            except Exception as e:
                notes.append(f"LLM-Parsing-Fehler: {e}")

    color = pick_color_heuristic(wine)
    legacy_note = notes[0] if notes else "(Heuristik/Regeln; LLM evtl. inaktiv)"

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
        color=color,
        hex=color.hex,
        rgb=[*color.rgb],
        note=legacy_note,
    )

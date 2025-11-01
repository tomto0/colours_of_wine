# backend/app.py
from __future__ import annotations

import os
import re
import ast
import json
from typing import List, Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# -------------------- optionale Gemini-Initialisierung -----------------------
_GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai  # type: ignore
    if os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        _GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_AVAILABLE = False

# ------------------------------- FastAPI/CORS --------------------------------
app = FastAPI(title="Colours of Wine API", version="0.2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------- Modelle -----------------------------------
class AnalyzeRequest(BaseModel):
    wine_name: str = Field(..., description='z. B. "Riesling Bürklin Otto Paus 2021"')

class SourceItem(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None

class ColorInfo(BaseModel):
    name: str
    hex: str
    rgb: Tuple[int, int, int]

class AnalyzeResponse(BaseModel):
    # neue, saubere Struktur
    wine_name: str
    found: bool
    color: ColorInfo
    notes: List[str] = []
    sources: List[SourceItem] = []
    reasoning: Optional[str] = None
    used_llm: bool = False

    # ---- Abwärtskompatibilität zu bestehendem Frontend ----
    # (dein Flutter-Code liest derzeit wohl diese Felder)
    hex: Optional[str] = None
    rgb: Optional[List[int]] = None
    note: Optional[str] = None

# -------------------------------- Utilities ----------------------------------
DDG_SAFE = os.getenv("DDG_SAFE", "moderate")

COLOR_TABLE: Dict[str, str] = {
    "pale straw": "#F6F2AF",
    "lemon": "#F4E04D",
    "gold": "#E0B129",
    "amber": "#C58C3B",
    "salmon": "#FFA07A",
    "onion skin": "#D48C78",
    "rosé": "#F4A6B0",
    "ruby": "#8B1A1A",
    "garnet": "#7B2D26",
    "brick": "#8B3A2B",
    "purple": "#5B2C6F",
    "tawny": "#AF6E4D",
}

def _rgb_from_hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore

HEURISTICS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(riesling|sauvignon|vermentino|pinot\s*grigio|grüner|albari[nñ]o)\b", re.I), "pale straw"),
    (re.compile(r"\b(chardonnay|viognier|marsanne|roussanne|semillon)\b", re.I), "lemon"),
    (re.compile(r"\b(gew[üu]rz|late harvest|sp[äa]tlese|sauternes|dessert|botrytis)\b", re.I), "gold"),
    (re.compile(r"\b(ros[eé]|grenache gris|clairet)\b", re.I), "rosé"),
    (re.compile(r"\b(pinot noir|chianti|sangiovese|nebbiolo|barolo|barbaresco)\b", re.I), "garnet"),
    (re.compile(r"\b(cabernet|merlot|malbec|tempranillo|shiraz|syrah)\b", re.I), "ruby"),
    (re.compile(r"\b(port|tawny|oxidative|oloroso|amontillado)\b", re.I), "tawny"),
]

def pick_color_heuristic(text: str) -> ColorInfo:
    for pattern, cname in HEURISTICS:
        if pattern.search(text):
            hx = COLOR_TABLE[cname]
            return ColorInfo(name=cname, hex=hx, rgb=_rgb_from_hex(hx))
    if re.search(r"\bros[eé]\b", text, re.I):
        hx = COLOR_TABLE["rosé"]
        return ColorInfo(name="rosé", hex=hx, rgb=_rgb_from_hex(hx))
    hx = COLOR_TABLE["ruby"]
    return ColorInfo(name="ruby", hex=hx, rgb=_rgb_from_hex(hx))

async def ddg_search(query: str, max_results: int = 6) -> List[SourceItem]:
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        print("[ddg] ddgs nicht installiert – Quellen werden leer sein.")
        return []

    results: List[SourceItem] = []
    try:
        with DDGS() as ddgs:
            print(f"[ddg] query: {query}")
            for r in ddgs.text(query, region="wt-wt", safesearch=DDG_SAFE, max_results=max_results):
                results.append(SourceItem(title=r.get("title"),
                                          url=r.get("href") or r.get("url"),
                                          snippet=r.get("body")))
        print(f"[ddg] results: {len(results)}")
    except Exception as e:
        print(f"[ddg] Fehler: {e} (Suche wird ignoriert)")
        return []
    return results

def _build_llm_prompt(wine_name: str, snippets: List[SourceItem]) -> str:
    lines = [
        "Aufgabe: Ermittele die typische Weinfarbe (z. B. pale straw, lemon, gold, salmon, rosé, ruby, garnet, brick, purple, tawny).",
        'Antworte NUR als JSON: {"color_name": str, "hex": str, "notes": [str], "reasoning": str}',
        f"Wein: {wine_name}",
        "Snippets:",
    ]
    for i, s in enumerate(snippets, 1):
        lines.append(f"{i}. {s.title or ''} — {s.snippet or ''} ({s.url or ''})")
    return "\n".join(lines)

def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
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
    if not _GEMINI_AVAILABLE:
        return None
    try:
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))  # type: ignore
        resp = await model.generate_content_async(prompt)  # type: ignore
        if hasattr(resp, "text"):
            return _parse_llm_json(resp.text)  # type: ignore
    except Exception as e:
        print(f"[gemini] Fehler: {e}")
    return None

# --------------------------------- Routes ------------------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "Colours of Wine API",
        "endpoints": {"health": "GET /health", "analyze": "POST /analyze  { wine_name: str }"},
    }

@app.get("/favicon.ico")
def favicon() -> Dict[str, Any]:
    return {}

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    # 1) Suche (fehlertolerant, geloggt)
    sources = await ddg_search(
        f'"{wine}" Wein OR Wine site:winemaker.com OR site:vivino.com OR site:wine.com OR site:wikipedia.org',
        max_results=6,
    )

    # 2) Heuristik
    color = pick_color_heuristic(wine)
    notes: List[str] = []
    reasoning = None
    used_llm = False

    # 3) Optional LLM-Refinement
    if _GEMINI_AVAILABLE:
        prompt = _build_llm_prompt(wine, sources)
        llm_json = await run_gemini(prompt)
        if llm_json:
            try:
                name = str(llm_json.get("color_name", color.name)).strip() or color.name
                hx = str(llm_json.get("hex", COLOR_TABLE.get(name, color.hex))).strip() or color.hex
                if not re.fullmatch(r"#?[0-9a-fA-F]{6}", hx):
                    hx = COLOR_TABLE.get(name, color.hex)
                if not hx.startswith("#"):
                    hx = "#" + hx
                color = ColorInfo(name=name, hex=hx, rgb=_rgb_from_hex(hx))
                notes = [str(x) for x in llm_json.get("notes", []) if isinstance(x, (str, int, float))]
                reasoning = (llm_json.get("reasoning") or "").strip() or None
                used_llm = True
            except Exception as e:
                print(f"[parse llm] Fehler: {e}")

    # 4) Abwärtskompatible Felder füllen
    legacy_note = notes[0] if notes else "(Heuristik oder sichere Defaults, LLM evtl. nicht aktiv)"

    resp = AnalyzeResponse(
        wine_name=wine,
        found=len(sources) > 0,
        color=color,
        notes=notes,
        sources=sources,
        reasoning=reasoning,
        used_llm=used_llm,
        # legacy:
        hex=color.hex,
        rgb=[color.rgb[0], color.rgb[1], color.rgb[2]],
        note=legacy_note,
    )
    return resp

# backend/app.py
"""
FastAPI-Backend für "Colours of Wine"
"""

from __future__ import annotations

import os
import re
import ast
import json
from typing import List, Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- optionale LLM-Initialisierung (Gemini) -----------------------------------
_GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai  # type: ignore
    if os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        _GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_AVAILABLE = False

# --- FastAPI & CORS -----------------------------------------------------------
app = FastAPI(title="Colours of Wine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # im Dev offen; in Prod gezielt setzen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Datenmodelle -------------------------------------------------------------
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
    wine_name: str
    found: bool
    color: ColorInfo
    notes: List[str] = []
    sources: List[SourceItem] = []
    reasoning: Optional[str] = None
    used_llm: bool = False

# --- Utilities ----------------------------------------------------------------
DDG_SAFE = os.getenv("DDG_SAFE", "moderate")  # off|moderate|strict


def _rgb_from_hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


# Ein kleines Farblexikon + heuristische Keywords
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
    """Einfache Heuristik: Rebsorten/Begriffe -> typische Farbe."""
    for pattern, color_name in HEURISTICS:
        if pattern.search(text):
            hex_code = COLOR_TABLE[color_name]
            return ColorInfo(name=color_name, hex=hex_code, rgb=_rgb_from_hex(hex_code))
    if re.search(r"\bros[eé]\b", text, re.I):
        hex_code = COLOR_TABLE["rosé"]
        return ColorInfo(name="rosé", hex=hex_code, rgb=_rgb_from_hex(hex_code))
    hex_code = COLOR_TABLE["ruby"]
    return ColorInfo(name="ruby", hex=hex_code, rgb=_rgb_from_hex(hex_code))


async def ddg_search(query: str, max_results: int = 6) -> List[SourceItem]:
    """Sucht mit ddgs (ohne API-Key)."""
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        try:
            # fallback: alte Bibliothek
            from ddgs import DDGS  # type: ignore
        except Exception:
            return []

    results: List[SourceItem] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, region="wt-wt", safesearch=DDG_SAFE, max_results=max_results):
            results.append(
                SourceItem(
                    title=r.get("title"),
                    url=r.get("href") or r.get("url"),
                    snippet=r.get("body"),
                )
            )
    return results


def _build_llm_prompt(wine_name: str, snippets: List[SourceItem]) -> str:
    lines = [
        "Aufgabe: Finde die wahrscheinliche Weinfarbe (z. B. pale straw, lemon, gold, salmon, rosé, ruby, garnet, brick, purple, tawny) für den genannten Wein.",
        'Antworte im JSON-Format: {"color_name": str, "hex": str, "notes": [str], "reasoning": str}',
        f"Wein: {wine_name}",
        "Snippets:",
    ]
    for i, s in enumerate(snippets, 1):
        lines.append(f"{i}. {s.title or ''} — {s.snippet or ''} ({s.url or ''})")
    lines.append("Nur JSON als Ausgabe.")
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
        model = genai.GenerativeModel(_GEMINI_MODEL)  # type: ignore
        resp = await model.generate_content_async(prompt)  # type: ignore
        if hasattr(resp, "text"):
            return _parse_llm_json(resp.text)  # type: ignore
        return None
    except Exception:
        return None

# --- Routen -------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "Colours of Wine API",
        "endpoints": {"health": "GET /health", "analyze": "POST /analyze { wine_name: str }"},
    }


@app.get("/favicon.ico")
def favicon() -> Dict[str, Any]:
    return {}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    wine = req.wine_name.strip()
    if not wine:
        raise HTTPException(status_code=400, detail="wine_name darf nicht leer sein.")

    # 1) Web-Suche
    sources = await ddg_search(
        f'"{wine}" Wein OR Wine site:winemaker.com OR site:vivino.com OR site:wine.com OR site:wikipedia.org',
        max_results=6,
    )

    # 2) LLM (wenn verfügbar) – sonst Heuristik
    used_llm = False
    color = pick_color_heuristic(wine)
    notes: List[str] = []
    reasoning: Optional[str] = None

    if _GEMINI_AVAILABLE:
        prompt = _build_llm_prompt(wine, sources)
        llm_json = await run_gemini(prompt)
        if llm_json:
            try:
                color_name = str(llm_json.get("color_name", color.name)).strip()
                hex_code = str(llm_json.get("hex", COLOR_TABLE.get(color_name, color.hex))).strip()
                if not re.fullmatch(r"#?[0-9a-fA-F]{6}", hex_code):
                    hex_code = COLOR_TABLE.get(color_name, color.hex)
                if not hex_code.startswith("#"):
                    hex_code = "#" + hex_code
                color = ColorInfo(name=color_name, hex=hex_code, rgb=_rgb_from_hex(hex_code))
                notes = [str(x) for x in llm_json.get("notes", []) if isinstance(x, (str, int, float))]
                reasoning = (llm_json.get("reasoning") or "").strip() or None
                used_llm = True
            except Exception:
                pass

    return AnalyzeResponse(
        wine_name=wine,
        found=len(sources) > 0,
        color=color,
        notes=notes or (["(Heuristik oder sichere Defaults, LLM evtl. nicht aktiv)"] if not used_llm else []),
        sources=sources,
        reasoning=reasoning,
        used_llm=used_llm,
    )

from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import GEMINI_KEY_SET
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    VizProfile,
)
from .heuristics import extract_props, pick_color_heuristic
from .search import _ddg_text, _rank_and_filter, _normalize_name, _DDGS_AVAILABLE
from .llm import (
    build_gemini,
    run_gemini,
    _build_llm_prompt_struct,
    _build_llm_prompt_from_name,
    _merge_props_non_destructive,
)

app = FastAPI(title="Colours of Wine API", version="0.9.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    full, base, vintage = _normalize_name(wine)

    tried: List[str] = []
    regions = ["de-de", "us-en"]
    queries = [
        f'"{full}"',
        f'"{base}" {vintage or ""} site:vivino.com OR site:winesearcher.com OR site:wine.com',
        f'{base} {vintage or ""} site:wikipedia.org OR site:falstaff.com OR site:wein.plus',
        f"{full} wine",
        full,
    ]

    sources = []
    used_query = queries[0]
    used_engine = "ddg:de-de"

    raw = []
    for q in queries:
        for reg in regions:
            tried.append(f"{reg} :: {q}")
            res = await _ddg_text(q, reg, max_results=12)
            if res:
                raw.extend(res)
        if raw:
            break

    if raw:
        from .search import _dedup_sources  # lokale Import, um Zyklus zu vermeiden

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

    props = extract_props(wine, sources)

    used_llm = False
    reasoning = None
    viz_profile: VizProfile | None = None

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

                props = _merge_props_non_destructive(props, llm_props)

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

    color = pick_color_heuristic(wine)

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

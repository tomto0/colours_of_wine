from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import GEMINI_KEY_SET
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    VizProfile,
    SourceItem,
)
from .heuristics import extract_props, pick_color_heuristic
from .llm import (
    build_gemini,
    run_full_pipeline_google_search,
    _merge_props_non_destructive,
)

app = FastAPI(title="Colours of Wine API", version="2.1.0")

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
        "search_mode": "google_search_via_gemini",
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Haupt-Logik mit Google Search via Gemini:

      1. Name normalisieren.
      2. Heuristische Props nur aus dem Namen (leichtgewichtig).
      3. Wenn `use_llm`:
           - Gemini + Google Search verwenden
           - vertrauenswürdige Quellen beachten
           - per_source-Summaries, combined_summary, props, viz
           - Props mit Heuristik mergen.
      4. Farbe via Heuristik, ggf. als Fallback-Farbe für viz.base_color_hex.
    """
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    notes: List[str] = []

    # 1) Heuristische Props aus dem Namen (ohne Websuche)
    heuristic_props = extract_props(wine, [])

    used_llm = False
    critic_summaries = []
    combined_summary = None
    viz_profile: VizProfile | None = None
    props_final = heuristic_props
    reasoning = None

    # 2) LLM + Google Search, wenn angefordert
    if req.use_llm:
        full = await run_full_pipeline_google_search(wine)
        if full:
            critic_summaries, combined_summary, llm_props, viz_profile = full

            # Heuristik nur ergänzen, nicht überschreiben
            props_final = _merge_props_non_destructive(heuristic_props, llm_props)
            used_llm = True
            reasoning = (
                "Gemini hat Google-Suche verwendet und Informationen aus den priorisierten "
                "Quellen (Weingüter, Magazine, Kritiker) aggregiert. "
                "Heuristische Werte wurden nur ergänzt, nicht überschrieben."
            )
        else:
            notes.append(
                "LLM- oder Google-Search-Pipeline fehlgeschlagen – nur heuristische Analyse aus dem Namen."
            )

    # 3) Farbe / Viz-Fallback
    color = pick_color_heuristic(wine)
    if viz_profile and not viz_profile.base_color_hex:
        viz_profile.base_color_hex = color.hex

    legacy_note = (
        "LLM-basierte Google-Search-Analyse (vertrauenswürdige Quellen)"
        if used_llm
        else (notes[0] if notes else "Heuristik/Regeln aus dem Namen")
    )

    # 4) Quellen für das Frontend aufbauen
    sources: List[SourceItem] = []
    if critic_summaries:
        for cs in critic_summaries:
            sources.append(
                SourceItem(
                    title=cs.source_label,
                    url=cs.url,
                    snippet=cs.summary,
                    score=None,
                )
            )

    found = used_llm  # wenn LLM lief, gehen wir von „gefunden“ aus

    return AnalyzeResponse(
        wine_name=wine,
        searched_query=wine,
        engine="gemini+google-search",
        tried_queries=[],  # keine manuellen Queries mehr
        found=found,
        props=props_final,
        sources=sources,
        notes=notes,
        used_llm=used_llm,
        reasoning=reasoning,
        viz=viz_profile,
        critic_summaries=critic_summaries,
        combined_summary=combined_summary,
        color=color,
        hex=color.hex,
        rgb=[*color.rgb],
        note=legacy_note,
    )

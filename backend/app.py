from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import GEMINI_KEY_SET, SEARCH_ENABLED
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
from .search import google_search_raw

app = FastAPI(title="Colours of Wine API", version="2.2.0")

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
        "search_mode": "google_custom_search+gemini",
        "search_enabled": SEARCH_ENABLED,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Haupt-Logik:

      1. Name normalisieren.
      2. Google Custom Search → Roh-Snippets (falls konfiguriert).
      3. Heuristische Props aus Name + Snippets.
      4. Optional: LLM-Pipeline (Summaries + Props + Viz) und Merge.
      5. Farbe als Fallback für Viz.
    """
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    notes: List[str] = []

    # ---------------------------------------------------------
    # 1) Google Custom Search: Roh-Snippets für Frontend & Heuristik
    # ---------------------------------------------------------
    sources: List[SourceItem] = []

    if SEARCH_ENABLED:
        try:
            raw_results = await google_search_raw(wine, num_results=8)
            for item in raw_results:
                sources.append(
                    SourceItem(
                        title=item.get("title"),
                        url=item.get("url"),
                        snippet=item.get("snippet"),
                        score=None,
                    )
                )
        except Exception as e:
            notes.append(f"Google Search fehlgeschlagen: {e}")
    else:
        notes.append(
            "Google Search ist nicht konfiguriert (GOOGLE_SEARCH_API_KEY oder GOOGLE_CSE_ID fehlen)."
        )

    # ---------------------------------------------------------
    # 2) Heuristik aus Namen + Snippets
    # ---------------------------------------------------------
    heuristic_props = extract_props(wine, sources)

    used_llm = False
    critic_summaries = []
    combined_summary = None
    viz_profile: VizProfile | None = None
    props_final = heuristic_props
    reasoning = None

    # ---------------------------------------------------------
    # 3) LLM-Pipeline (Gemini) optional
    # ---------------------------------------------------------
    if req.use_llm:
        full = await run_full_pipeline_google_search(wine)
        if full:
            critic_summaries, combined_summary, llm_props, viz_profile = full

            # Heuristik nur ergänzen, nicht überschreiben
            props_final = _merge_props_non_destructive(heuristic_props, llm_props)
            used_llm = True
            reasoning = (
                "Gemini hat (sein Wissen und ggf. interne Websuche) verwendet, um Informationen "
                "aus priorisierten Quellen zu aggregieren. Heuristische Werte wurden nur ergänzt, "
                "nicht überschrieben."
            )
        else:
            notes.append(
                "LLM-Pipeline fehlgeschlagen – nur heuristische Analyse aus Namen + Google-Snippets."
            )

    # ---------------------------------------------------------
    # 4) Farbe & Viz-Fallback
    # ---------------------------------------------------------
    color = pick_color_heuristic(wine)
    if viz_profile and not viz_profile.base_color_hex:
        viz_profile.base_color_hex = color.hex

    legacy_note = (
        "LLM-basierte Analyse mit priorisierten Quellen"
        if used_llm
        else (notes[0] if notes else "Heuristik/Regeln aus Namen + Google-Snippets")
    )

    # „Gefunden“, wenn entweder Snippets oder LLM-Ergebnisse da sind
    found = bool(sources) or used_llm

    return AnalyzeResponse(
        wine_name=wine,
        searched_query=wine,
        engine="google-custom-search+gemini",
        tried_queries=[],
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

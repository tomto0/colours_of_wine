from __future__ import annotations

import io
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

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
from .imagegen import generate_wine_png_bytes
from .cache import get_cached_wine, save_to_cache, get_cache_stats

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
    stats = get_cache_stats()
    return {
        "status": "ok",
        "llm_available": bool(model),
        "gemini_model": chosen,
        "api_key_set": GEMINI_KEY_SET,
        "search_mode": "google_custom_search+gemini",
        "search_enabled": SEARCH_ENABLED,
        "cache_entries": stats["total_entries"],
    }


@app.get("/cache/stats")
def cache_stats():
    """Gibt Statistiken über den Wine-Cache zurück."""
    return get_cache_stats()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Haupt-Logik:

      1. Name normalisieren.
      2. **Cache prüfen** - bei Treffer direkt zurückgeben.
      3. Google Custom Search → Roh-Snippets (falls konfiguriert).
      4. Heuristische Props aus Name + Snippets.
      5. Optional: LLM-Pipeline (Summaries + Props + Viz) und Merge.
      6. Farbe als Fallback für Viz.
      7. **Ergebnis im Cache speichern.**
    """
    wine = (req.wine_name or "").strip()
    if not wine:
        raise HTTPException(status_code=400, detail="`wine_name` darf nicht leer sein.")

    notes: List[str] = []

    # ---------------------------------------------------------
    # 0) Cache prüfen - bei LLM-Anfrage und Treffer: sofort zurück
    # ---------------------------------------------------------
    cached = get_cached_wine(wine)
    if cached and req.use_llm:
        # Wein wurde schon mal mit LLM analysiert → Cache nutzen
        notes.append("✓ Ergebnis aus Cache geladen (bereits analysiert)")
        
        # VizProfile aus gecachten Daten rekonstruieren
        cached_viz = None
        if cached.get("viz"):
            cached_viz = VizProfile(**cached["viz"])
        
        # Farbe als Fallback
        color = pick_color_heuristic(wine)
        hex_color = cached.get("hex") or color.hex
        
        return AnalyzeResponse(
            wine_name=wine,
            searched_query=wine,
            engine="cache",
            tried_queries=[],
            found=True,
            props=cached.get("props", {}),
            sources=[],  # Quellen nicht gecacht
            notes=notes,
            used_llm=True,  # War mal LLM
            reasoning=f"Aus Cache geladen (gespeichert: {cached.get('created_at', 'unbekannt')})",
            viz=cached_viz,
            critic_summaries=[],  # Nicht gecacht
            combined_summary=cached.get("combined_summary"),
            color=color,
            hex=hex_color,
            rgb=[*color.rgb],
            note="Gecachte LLM-Analyse",
        )

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

    # „Gefunden", wenn entweder Snippets oder LLM-Ergebnisse da sind
    found = bool(sources) or used_llm

    # ---------------------------------------------------------
    # 5) Ergebnis im Cache speichern (nur bei LLM-Nutzung)
    # ---------------------------------------------------------
    if used_llm:
        # props_final zu dict konvertieren (kann WineProps Pydantic-Model sein)
        props_dict = props_final.model_dump() if hasattr(props_final, 'model_dump') else props_final
        save_to_cache(
            wine_name=wine,
            viz_profile=viz_profile.model_dump() if viz_profile else None,
            combined_summary=combined_summary,
            props=props_dict,
            hex_color=color.hex,
        )
        notes.append("✓ Ergebnis im Cache gespeichert")

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


# ---------------------------------------------------------
# Neuer Endpoint: Visualisierung als PNG generieren
# ---------------------------------------------------------

class VizRequest(BaseModel):
    """Eingabe für /generate-viz - alle Werte 0..1"""
    base_color_hex: str = "#F6F2AF"
    acidity: float = 0.5
    body: float = 0.5
    depth: float = 0.5
    oak_intensity: float = 0.0
    mineral_intensity: float = 0.3
    herbal_intensity: float = 0.0
    spice_intensity: float = 0.0
    fruit_citrus: float = 0.0
    fruit_stone: float = 0.0
    fruit_tropical: float = 0.0
    fruit_red: float = 0.0
    fruit_dark: float = 0.0
    effervescence: float = 0.0
    residual_sugar: float = 0.0  # Restzucker in g/L
    wine_type: str = "auto"  # "red", "white", "rose", "auto"
    size: int = 512
    summary: Optional[str] = None  # Die kombinierte Zusammenfassung des Weins


@app.post("/generate-viz")
async def generate_viz(req: VizRequest) -> Response:
    """
    Generiert ein PNG-Bild der Weinvisualisierung.
    Gibt das Bild direkt als image/png zurück.
    
    Der 'summary' Parameter enthält die kombinierte Zusammenfassung des Weins,
    die für erweiterte Visualisierungen oder Logging verwendet werden kann.
    """
    viz_dict = {
        "base_color_hex": req.base_color_hex,
        "acidity": req.acidity,
        "body": req.body,
        "depth": req.depth,
        "oak_intensity": req.oak_intensity,
        "mineral_intensity": req.mineral_intensity,
        "herbal_intensity": req.herbal_intensity,
        "spice_intensity": req.spice_intensity,
        "fruit_citrus": req.fruit_citrus,
        "fruit_stone": req.fruit_stone,
        "fruit_tropical": req.fruit_tropical,
        "fruit_red": req.fruit_red,
        "fruit_dark": req.fruit_dark,
        "effervescence": req.effervescence,
        "residual_sugar": req.residual_sugar,
        "wine_type": req.wine_type,
        "summary": req.summary,  # Für zukünftige Nutzung in imagegen
    }
    
    try:
        png_bytes = generate_wine_png_bytes(viz_dict, size=req.size)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bildgenerierung fehlgeschlagen: {e}")

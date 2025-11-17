from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, Optional, List, Tuple

from .config import (
    GEMINI_MODEL_ENV,
    GOOGLE_API_KEY,
    GEMINI_KEY_SET,
    PREFERRED_MODELS,
    PRIORITY_SOURCES,
)
from .models import VizProfile, WineProps, CriticSummary

# =====================================================================
#  Gemini-Setup
# =====================================================================

_genai = None
try:
    import google.generativeai as genai  # type: ignore

    _genai = genai
    if GEMINI_KEY_SET:
        _genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    _genai = None


def build_gemini() -> Tuple[Optional[Any], Optional[str]]:
    """
    Baue ein konfiguriertes Gemini-Model-Objekt + den gewählten Modellnamen.

    WICHTIG:
      - Kein 'tools' / google_search hier, weil deine aktuelle SDK-Version
        das (noch) nicht unterstützt.
      - Wir erzwingen JSON-Ausgabe über 'response_mime_type', damit das
        Modell direkt validen JSON-Text zurückgibt.
    """
    if not (_genai and GEMINI_KEY_SET):
        return None, None

    try:
        available = list(_genai.list_models())
        # Modelle filtern, die generateContent unterstützen
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

        chosen_name: Optional[str] = None
        for cand in candidates:
            avail = is_available(cand)
            if avail:
                chosen_name = avail
                break

        if not chosen_name and available_gc:
            # Fallback: erstes Modell mit generateContent
            chosen_name = sorted(available_gc)[0]

        if not chosen_name:
            return None, None

        model = _genai.GenerativeModel(
            chosen_name,
            generation_config={
                # Sagt dem Modell: „Bitte gib direkt JSON als Text zurück“
                "response_mime_type": "application/json",
                "temperature": 0.3,
            },
        )
        return model, chosen_name

    except Exception as e:
        print(f"[gemini] Fehler beim Listen/Wählen der Modelle: {e}")

    return None, None


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """
    LLM-Text → JSON (robust, auch wenn das Modell doch etwas drumherum schreibt).
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    # Fallback: erstes {...}-Objekt herausziehen
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
    Führt einen Prompt mit Gemini aus und versucht, JSON zu parsen.
    """
    model, chosen = build_gemini()
    if not model:
        print("[gemini] Kein Modell verfügbar oder kein API-Key gesetzt.")
        return None

    try:
        print(f"[gemini] using model: {chosen}")
        resp = await model.generate_content_async(prompt)  # type: ignore

        # Bei response_mime_type = application/json sollte das hier JSON sein:
        text = getattr(resp, "text", None)
        if not text:
            print("[gemini] Leere Antwort.")
            return None

        data = _parse_llm_json(text)
        if data is None:
            print(f"[gemini] Konnte JSON nicht parsen. Raw:\n{text[:500]}...")
        return data
    except Exception as e:
        print(f"[gemini] Fehler: {e}")
        return None


# =====================================================================
#  Prompt-Bau
# =====================================================================

def build_search_grounded_prompt(wine_name: str) -> str:
    """
    Prompt, der dem Modell beschreibt, dass es sein Wissen (und ggf. interne
    Web-/Suche-Möglichkeiten) nutzen soll, um Infos aus deinen priorisierten
    Quellen zu aggregieren.

    Wir aktivieren KEIN Tool explizit, aber geben die Quellen & Struktur vor.
    """
    lines: List[str] = [
        "Du bist ein hochspezialisierter Weinkritiker und Datenaggregator.",
        f'Der Wein lautet: "{wine_name}".',
        "",
        "Nutze dein aktuelles Wissen und, falls verfügbar, interne Web-/Suchfunktionen,",
        "um gezielt Informationen zu genau diesem Wein zu recherchieren.",
        "",
        "Verwende bevorzugt die folgenden vertrauenswürdigen Quellen (in dieser Reihenfolge),",
        "soweit du dazu Informationen hast:",
    ]

    for src in PRIORITY_SOURCES:
        label = src["label"]
        domains = src.get("domains") or []
        if domains:
            lines.append(f"- {label} (Domains: {', '.join(domains)})")
        else:
            lines.append(f"- {label}")

    lines.extend(
        [
            "",
            "Verwende diese Quellen (soweit du über sie Wissen hast), um:",
            "- technische Daten (Weingut, Lage, Rebsorten, Alkohol, Stil, Süße, etc.)",
            "- professionelle Verkostungsnotizen",
            "- Qualitätsbeschreibungen und Bewertungen",
            "zu diesem konkreten Wein zu liefern.",
            "",
            "Gib **ausschließlich** JSON zurück mit folgendem Schema (ohne zusätzlichen Text):",
            "{",
            '  "per_source": [',
            '    { "source_id": str, "source_label": str, "url": str|null, "summary": str }',
            "  ],",
            '  "combined_summary": str,',
            '  "props": {',
            '    "vintage": int|null,',
            '    "wine_type": "red"|"white"|"rosé"|"sparkling"|null,',
            '    "variety": str|null, "grapes": [str], "country": str|null, "region": str|null,',
            '    "appellation": str|null, "producer": str|null, "style": str|null, "sweetness": str|null,',
            '    "alcohol": float|null, "oak": bool|null, "tasting_notes": [str]',
            "  },",
            '  "viz": {',
            '    "base_color_hex": str|null, "acidity": float, "body": float, "tannin": float,',
            '    "depth": float, "sweetness": float, "oak": float, "bubbles": bool,',
            '    "fruit": [str], "non_fruit": [str], "mineral": float, "ripe_aromas": float',
            "  }",
            "}",
            "",
            "Hinweise:",
            "- per_source: fasse pro relevanter Quelle (Weingut, Vinum, Falstaff, ...) die wichtigsten Aussagen",
            "  in 2–4 Sätzen zusammen. Wenn du zu einer Quelle nichts Konkretes weißt, kannst du sie weglassen.",
            "- combined_summary: aggregiere alle Quellen zu einer konsistenten Gesamtbeschreibung (~5–10 Sätze).",
            "- props: wenn exakte Werte fehlen (z. B. Alkohol %), verwende plausible typische Werte",
            "  für diesen Weinstil und Jahrgang.",
            "- viz: alle numerischen Werte im Intervall [0.0, 1.0].",
        ]
    )

    return "\n".join(lines)


# =====================================================================
#  Voll-Pipeline: Summaries + Props + Viz
# =====================================================================

async def run_full_pipeline_google_search(
        wine_name: str,
) -> Optional[Tuple[List[CriticSummary], str, WineProps, VizProfile]]:
    """
    Komplette Pipeline über Gemini:

      - per_source-Summaries (pro Quelle Kurzfassung)
      - combined_summary (Gesamtzusammenfassung)
      - strukturierte props
      - viz-Profile

    Hinweis: der Name bleibt 'google_search', damit dein app.py kompatibel
    bleibt, auch wenn wir kein explizites Search-Tool konfigurieren.
    """
    prompt = build_search_grounded_prompt(wine_name)
    data = await run_gemini(prompt)
    if not data:
        return None

    try:
        per_src_raw = data.get("per_source") or []
        critic_summaries: List[CriticSummary] = []
        for item in per_src_raw:
            critic_summaries.append(
                CriticSummary(
                    source_id=str(item.get("source_id") or ""),
                    source_label=str(item.get("source_label") or ""),
                    url=item.get("url"),
                    summary=item.get("summary"),
                )
            )

        combined_summary = data.get("combined_summary") or ""

        llm_props_dict = data.get("props") or {}
        llm_viz_dict = data.get("viz") or {}

        llm_props = WineProps(**llm_props_dict)
        vp = VizProfile(**llm_viz_dict)
        vp.clamp()

        # Wir geben hier bewusst ein WineProps-Objekt zurück,
        # _merge_props_non_destructive kann jetzt damit umgehen.
        return critic_summaries, combined_summary, llm_props, vp
    except Exception as e:
        print(f"[gemini] Fehler beim Parsing des JSON: {e}")
        return None


# =====================================================================
#  Props-Merge: Heuristik + LLM
# =====================================================================

def _merge_props_non_destructive(base: WineProps, llm_props: Any) -> WineProps:
    """
    LLM-Props in bestehende Props mergen, ohne vorhandene Werte zu überschreiben.

    llm_props darf ein Dict oder ein WineProps-Objekt sein.
    """
    # Neu: robust gegen WineProps oder dict
    if isinstance(llm_props, WineProps):
        llm_dict = llm_props.model_dump()
    elif isinstance(llm_props, dict):
        llm_dict = llm_props
    else:
        # Unbekannter Typ -> nichts mergen
        return base

    merged = base.model_dump()

    def is_missing(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, list):
            return len(v) == 0
        return False

    for k, v in llm_dict.items():
        if k in ("grapes", "tasting_notes"):
            base_list = merged.get(k) or []
            if isinstance(v, list):
                merged[k] = sorted({*(str(x) for x in base_list), *(str(x) for x in v)})
            else:
                merged[k] = base_list
            continue

        cur = merged.get(k, None)

        if cur is None and v is not None:
            merged[k] = v
            continue

        if is_missing(cur) and v not in (None, "", []):
            merged[k] = v

    return WineProps(**merged)

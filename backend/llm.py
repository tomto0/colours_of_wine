from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, Optional, List, Tuple

from .config import (
    GEMINI_MODEL_ENV,
    GEMINI_API_KEY,
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
        _genai.configure(api_key=GEMINI_API_KEY)
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
    Prompt für detaillierte Weinanalyse mit strukturierter Zusammenfassung
    und präzisen Visualisierungsparametern.
    """
    lines: List[str] = [
        "Du bist ein erfahrener Sommelier und Weinkritiker mit tiefgreifendem Wissen über internationale Weine.",
        f'Analysiere den folgenden Wein: "{wine_name}"',
        "",
        "═══════════════════════════════════════════════════════════════",
        "TEIL 1: RECHERCHE UND QUELLEN",
        "═══════════════════════════════════════════════════════════════",
        "",
        "Recherchiere Informationen aus diesen vertrauenswürdigen Quellen:",
    ]

    for src in PRIORITY_SOURCES[:10]:  # Top 10 Quellen
        label = src["label"]
        lines.append(f"  • {label}")

    lines.extend([
        "",
        "Für jede Quelle mit relevanten Informationen erstelle eine Zusammenfassung:",
        "- Was sagt die Quelle über Herkunft, Rebsorte und Anbau?",
        "- Welche Verkostungsnotizen werden genannt (Aromen, Geschmack)?",
        "- Gibt es Bewertungen oder Qualitätseinschätzungen?",
        "",
        "═══════════════════════════════════════════════════════════════",
        "TEIL 2: GESAMTZUSAMMENFASSUNG (combined_summary)",
        "═══════════════════════════════════════════════════════════════",
        "",
        "Erstelle eine AUSFÜHRLICHE Gesamtbeschreibung (mindestens 8-12 Sätze) mit:",
        "",
        "1. HERKUNFT & ERZEUGER (2-3 Sätze):",
        "   - Weingut/Produzent und dessen Philosophie",
        "   - Anbaugebiet, Lage, Terroir",
        "   - Besonderheiten des Jahrgangs",
        "",
        "2. REBSORTE & AUSBAU (2-3 Sätze):",
        "   - Rebsorte(n) und deren Charakteristik",
        "   - Vinifikation (Stahl, Holz, Maischegärung etc.)",
        "   - Ausbaudauer und Reifepotential",
        "",
        "3. SENSORIK - AUSSEHEN (1-2 Sätze):",
        "   - Farbe und Farbintensität",
        "   - Klarheit, Viskosität",
        "",
        "4. SENSORIK - NASE (2-3 Sätze):",
        "   - Primäraromen (Frucht)",
        "   - Sekundäraromen (Gärung, Hefe)",
        "   - Tertiäraromen (Reife, Holz)",
        "",
        "5. SENSORIK - GAUMEN (2-3 Sätze):",
        "   - Geschmacksprofil und Harmonie",
        "   - Struktur: Säure, Tannin, Körper",
        "   - Abgang und Länge",
        "",
        "6. GESAMTEINDRUCK (1-2 Sätze):",
        "   - Qualitätseinschätzung",
        "   - Trinkfenster und Speiseempfehlung",
        "",
        "═══════════════════════════════════════════════════════════════",
        "TEIL 3: VISUALISIERUNGSPARAMETER (viz)",
        "═══════════════════════════════════════════════════════════════",
        "",
        "Die viz-Werte steuern eine künstlerische Weinvisualisierung.",
        "ALLE Werte sind Pflicht und müssen aus der Sensorik abgeleitet werden!",
        "",
        "WEINFARBE (base_color_hex) - wähle passend:",
        "  Weißwein:",
        "    #F0F5B8 - blassgelb/grünstichig (jung, leicht)",
        "    #E8ED89 - strohgelb mit Grünreflex (Grüner Veltliner, Riesling)",
        "    #F6F2AF - helles Strohgelb (klassisch)",
        "    #E6C75B - goldgelb (reif, Chardonnay im Holz)",
        "    #D4A84B - tiefgold (edelsüß, gereift)",
        "    #E8C070 - bernstein (TBA, Eiswein, Orange Wine)",
        "  Roséwein:",
        "    #FFD1DC - blasses Rosa (Provence-Stil)",
        "    #F4A6B0 - lachsrosa",
        "    #E8A0A0 - kräftiges Rosa",
        "  Rotwein:",
        "    #C41E3A - helles Rubinrot (Pinot Noir, jung)",
        "    #8B1A1A - mittleres Rubinrot (klassisch)",
        "    #722F37 - Granatrot (gereift)",
        "    #5A1A1A - dunkles Granat (Syrah, Malbec)",
        "    #3A0A0A - fast schwarz (Primitivo, Amarone)",
        "",
        "WEINTYP (wine_type): 'red', 'white' oder 'rose' - PFLICHT!",
        "",
        "STRUKTUR (0.0-1.0):",
        "  acidity:   0.2-0.4 weich | 0.5-0.6 frisch | 0.7-0.9 knackig/stahlig",
        "  body:      0.2-0.3 leicht | 0.4-0.5 mittel | 0.6-0.8 vollmundig | 0.9 opulent",
        "  tannin:    0.0 (Weißwein) | 0.2-0.4 seidig | 0.5-0.7 griffig | 0.8+ fest",
        "  depth:     0.2-0.4 einfach | 0.5-0.6 vielschichtig | 0.7-0.9 komplex",
        "  sweetness: 0.0-0.1 trocken | 0.2-0.3 feinherb | 0.4-0.6 halbtrocken | 0.7+ süß",
        "",
        "FRUCHTAROMEN (0.0-1.0) - setze passend zum Weintyp:",
        "  fruit_citrus:   Zitrone, Limette, Grapefruit (Weißwein, v.a. Riesling, Sauvignon)",
        "  fruit_stone:    Pfirsich, Aprikose, Nektarine (Weißwein, Rosé)",
        "  fruit_tropical: Mango, Ananas, Maracuja, Litschi (aromatische Sorten)",
        "  fruit_red:      Erdbeere, Himbeere, Kirsche (Rosé, Pinot Noir, Zweigelt)",
        "  fruit_dark:     Brombeere, Cassis, Pflaume, Schwarzkirsche (kräftige Rotweine)",
        "",
        "WEITERE AROMEN (0.0-1.0):",
        "  herbal_intensity:  Kräuter, Gras, grüne Paprika, Minze, Eukalyptus",
        "  spice_intensity:   Pfeffer, Zimt, Nelke, Vanille, Lakritze",
        "  mineral_intensity: Feuerstein, Schiefer, Salz, Kreide, nasser Stein",
        "  oak_intensity:     Holz, Toast, Röstaromen, Karamell, Kokos",
        "",
        "PERLAGE:",
        "  effervescence: 0.0 still | 0.2-0.4 leicht perlend | 0.5-0.7 Frizzante | 0.8-1.0 Sekt/Champagner",
        "  bubbles: true nur bei Schaumwein/Sekt/Champagner/Crémant/Prosecco",
        "",
        "RESTZUCKER (SEHR WICHTIG für Geschmack!):",
        "  residual_sugar: Restzucker in Gramm pro Liter (g/L)",
        "    - Trocken (dry): 0-9 g/L",
        "    - Halbtrocken (off-dry): 10-18 g/L", 
        "    - Lieblich (medium-sweet): 19-45 g/L",
        "    - Süß (sweet): 46-100 g/L",
        "    - Edelsüß (very sweet, z.B. TBA, Eiswein): 100-500+ g/L",
        "  Falls keine genaue Angabe verfügbar, schätze anhand der Stilbezeichnung!",
        "",
        "═══════════════════════════════════════════════════════════════",
        "JSON-AUSGABE",
        "═══════════════════════════════════════════════════════════════",
        "",
        "Gib NUR valides JSON zurück (kein anderer Text!):",
        "{",
        '  "per_source": [',
        '    {',
        '      "source_id": "producer|vinum|falstaff|...",',
        '      "source_label": "Name der Quelle",',
        '      "url": "URL falls bekannt, sonst null",',
        '      "summary": "Ausführliche Zusammenfassung der Quelle (3-5 Sätze)"',
        '    }',
        "  ],",
        '  "combined_summary": "Ausführliche Gesamtbeschreibung (8-12 Sätze, siehe oben)",',
        '  "props": {',
        '    "vintage": 2022,',
        '    "wine_type": "white",',
        '    "variety": "Grüner Veltliner",',
        '    "grapes": ["Grüner Veltliner"],',
        '    "country": "Austria",',
        '    "region": "Wachau",',
        '    "appellation": "Smaragd",',
        '    "producer": "Weingut XY",',
        '    "style": "trocken",',
        '    "sweetness": "dry",',
        '    "alcohol": 13.5,',
        '    "oak": false,',
        '    "tasting_notes": ["Steinobst", "Zitrus", "mineralisch", "würzig"]',
        "  },",
        '  "viz": {',
        '    "base_color_hex": "#E8ED89",',
        '    "wine_type": "white",',
        '    "acidity": 0.75,',
        '    "body": 0.55,',
        '    "tannin": 0.0,',
        '    "depth": 0.65,',
        '    "sweetness": 0.05,',
        '    "oak_intensity": 0.1,',
        '    "mineral_intensity": 0.6,',
        '    "herbal_intensity": 0.4,',
        '    "spice_intensity": 0.35,',
        '    "fruit_citrus": 0.5,',
        '    "fruit_stone": 0.6,',
        '    "fruit_tropical": 0.2,',
        '    "fruit_red": 0.0,',
        '    "fruit_dark": 0.0,',
        '    "effervescence": 0.0,',
        '    "bubbles": false,',
        '    "residual_sugar": 5.0',
        "  }",
        "}",
        "",
        "WICHTIG:",
        "- combined_summary MUSS mindestens 8 Sätze haben und alle 6 Bereiche abdecken!",
        "- viz-Werte müssen die Sensorik-Beschreibung widerspiegeln",
        "- Alle Felder sind Pflicht, keine null-Werte bei viz!",
    ])

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

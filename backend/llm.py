import ast
import json
import re
from typing import Any, Dict, Optional, List, Tuple

from .config import GEMINI_MODEL_ENV, GOOGLE_API_KEY, GEMINI_KEY_SET, PREFERRED_MODELS
from .models import VizProfile, WineProps, SourceItem

_genai = None
try:
    import google.generativeai as genai  # type: ignore

    _genai = genai
    if GEMINI_KEY_SET:
        _genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    _genai = None


def build_gemini() -> Tuple[Optional[Any], Optional[str]]:
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
        "Snippets (nur zur Ableitung):",
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


def _merge_props_non_destructive(base: WineProps, llm_props: Dict[str, Any]) -> WineProps:
    merged = base.model_dump()

    def is_missing(v: Any) -> bool:
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

        if cur is None and v is not None:
            merged[k] = v
            continue

        if is_missing(cur) and v not in (None, "", []):
            merged[k] = v

    return WineProps(**merged)

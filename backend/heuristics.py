from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .config import COLOR_TABLE, COUNTRIES, VARIETIES, SWEET_WORDS, SPARK_WORDS, OAK_WORDS
from .models import WineProps, ColorInfo, SourceItem


def _rgb_from_hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def pick_color_heuristic(text: str) -> ColorInfo:
    """
    Grobe Farbauswahl nur aus dem Weinnamen.
    """
    t = text.lower()
    if any(k in t for k in ["riesling", "grüner", "sauvignon", "pinot grigio", "albari", "vermentino"]):
        name = "pale straw"
    elif "rosé" in t or "rose" in t:
        name = "rosé"
    elif any(k in t for k in ["nebbiolo", "sangiovese", "chianti"]):
        name = "garnet"
    else:
        name = "ruby"
    hx = COLOR_TABLE[name]
    return ColorInfo(name=name, hex=hx, rgb=_rgb_from_hex(hx))


def _first_match(pat: str, text: str, flags=re.I) -> Optional[str]:
    m = re.search(pat, text, flags)
    return m.group(1) if m else None


def extract_props(wine_name: str, sources: List[SourceItem]) -> WineProps:
    """
    Extrahiere Basis-Eigenschaften aus Namen + Snippets per Regex-Heuristik.
    """
    blob_parts = [wine_name] + [s.title or "" for s in sources] + [s.snippet or "" for s in sources]
    blob = "\n".join(blob_parts)
    props = WineProps()

    # Vintage
    vin = _first_match(r"\b(19[6-9]\d|20[0-4]\d)\b", blob)
    if vin:
        props.vintage = int(vin)

    # Produzent
    prod = _first_match(
        r"(Weingut\s+[A-ZÄÖÜ][\w\-\s]+?|[A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+){0,3})\s+("
        r"Riesling|Chardonnay|Pinot|Sauvignon|Grüner|Blaufränkisch|Zweigelt|Sangiovese|"
        r"Nebbiolo|Merlot|Cabernet)",
        blob,
    )
    if prod:
        props.producer = prod.strip()

    # Land
    for c in COUNTRIES:
        if re.search(r"\b" + re.escape(c) + r"\b", blob, re.I):
            props.country = c
            break

    # Region
    reg = _first_match(
        r"\b(Pfalz|Mosel|Wachau|Kamptal|Ahr|Nahe|Rheingau|Tuscany|Burgundy|Bordeaux|Rioja|Mendoza)\b",
        blob,
    )
    if reg:
        props.region = reg

    # Sorte + Typ
    for v, typ in VARIETIES:
        if re.search(r"\b" + re.escape(v) + r"\b", blob, re.I):
            props.variety = v
            props.wine_type = {"white": "white", "red": "red"}[typ]
            props.grapes = [v]
            break

    # Rosé-Fallback
    if not props.wine_type and re.search(r"\bros[ée]\b", blob, re.I):
        props.wine_type = "rosé"

    # Stil
    props.style = (
        "sparkling"
        if any(re.search(r"\b" + w + r"\b", blob, re.I) for w in SPARK_WORDS)
        else "still"
    )
    if re.search(r"\b(port|sherry|madeira)\b", blob, re.I):
        props.style = "fortified"

    # Süße
    for de, en in SWEET_WORDS:
        if re.search(r"\b" + de + r"\b", blob, re.I):
            props.sweetness = en
            break

    # Alkohol
    alc = (
            _first_match(r"(\d{1,2}(?:[.,]\d)?)\s*%\s*(?:vol|abv)\b", blob)
            or _first_match(r"(?:alkohol|alc\.?|alcohol)\s*[:=]??\s*(\d{1,2}(?:[.,]\d)?)\s*%", blob)
            or _first_match(r"(\d{1,2}(?:[.,]\d)?)\s*%", blob)
    )
    if alc:
        try:
            props.alcohol = float(alc.replace(",", "."))
        except Exception:
            pass

    # Holz
    if any(re.search(r"\b" + w + r"\b", blob, re.I) for w in OAK_WORDS):
        props.oak = True

    # Tasting Notes
    tn = re.findall(
        r"\b(apple|pear|peach|citrus|lemon|lime|apricot|pineapple|herb|spice|vanilla|cherry|"
        r"raspberry|strawberry|plum|pepper|smoke|mineral)\b",
        blob,
        re.I,
    )
    if tn:
        props.tasting_notes = sorted(set([t.lower() for t in tn]))
    return props

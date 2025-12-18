from __future__ import annotations

"""Hilfsskript: generiert für alle Weine in `bsp/` Beispiel-PNGs.

Es liest die Texte aus `bsp/01/text01.txt`, `bsp/02/text02.txt`, ...
leitet daraus ein grobes Viz-Profil ab und ruft `imagegen.generate_wine_png`.

Dies ist bewusst heuristisch und dient als Startpunkt, um die
Parameter an den gezeichneten Beispielen zu kalibrieren.
"""

from pathlib import Path
import re
from typing import Dict

from imagegen import generate_wine_png


ROOT = Path(__file__).resolve().parent.parent
BSP_DIR = ROOT / "bsp"
OUT_DIR = ROOT / "backend" / "generated_bsp"


def _score(text: str, words: list[str]) -> float:
    t = text.lower()
    hits = sum(1 for w in words if w in t)
    return min(1.0, hits / max(1, len(words)))


def profile_from_text(txt: str) -> Dict:
    """Sehr grobe Heuristik: Text → Viz-Profil-ähnliches Dict.

    Ziel: erste Näherung, die wir visuell an euren Zeichnungen
    ausrichten können. Später kann das durch einen LLM-Agenten
    ersetzt oder ergänzt werden.
    """

    t = txt.lower()

    # === Basisfarbe: Zuerst Weintyp bestimmen ===
    
    # Rosé erkennen
    is_rose = any(k in t for k in ["rosé", "rose ", "lachsrosa", "rosa"])
    
    # Rotwein erkennen (Rebsorten und Beschreibungen)
    red_grapes = ["pinot noir", "merlot", "cabernet", "blaufränkisch", "zweigelt", 
                  "sangiovese", "nebbiolo", "tempranillo", "syrah", "shiraz",
                  "grenache", "mourvèdre", "tignanello", "st. laurent"]
    red_descriptors = ["rubinrot", "purpur", "violett", "dunkelrot", "schwarz-violett",
                       "rubin", "granat", "tiefdunkel", "kirschrot"]
    is_red = any(k in t for k in red_grapes) or any(k in t for k in red_descriptors)
    
    # Weißwein erkennen (Rebsorten)
    white_grapes = ["chardonnay", "riesling", "sauvignon blanc", "grüner veltliner",
                    "weißburgunder", "pinot grigio", "pinot gris", "welschriesling",
                    "gewürztraminer", "muskateller", "grauburgunder", "albariño"]
    white_descriptors = ["zitronengelb", "grüngelb", "strohgelb", "goldgelb", 
                         "blassgelb", "hellgelb", "grünliche reflexe"]
    is_white = any(k in t for k in white_grapes) or any(k in t for k in white_descriptors)
    
    # Süßwein/Amber erkennen
    is_sweet_amber = any(k in t for k in ["trockenbeerenauslese", "beerenauslese", 
                                           "eiswein", "auslese", "bernstein", 
                                           "amber", "goldgelb mit bernstein"])

    # Basisfarbe zuweisen
    wine_type = "auto"
    if is_rose:
        base_color = "#C8857F"  # Lachsrosa (etwas dunkler)
        wine_type = "rose"
    elif is_red:
        # WICHTIG: Spezifische Rebsorten ZUERST prüfen, dann allgemeine Beschreibungen
        if "pinot noir" in t:
            base_color = "#8A3050"  # Mittleres Rubin (Pinot Noir) - wird außen aufgehellt
        elif "zweigelt" in t:
            base_color = "#8A2540"  # Mittleres Rubin-Violett (Zweigelt)
        elif any(k in t for k in ["tignanello", "sangiovese"]):
            base_color = "#6B1528"  # Mittel-dunkel (Toskana)
        elif any(k in t for k in ["tiefdunkel", "schwarz", "dicht", "ducru", "château"]):
            base_color = "#4A0D1C"  # Sehr dunkel (Bordeaux etc.)
        else:
            base_color = "#7A1024"  # Standard Rot
    elif is_sweet_amber:
        base_color = "#E8C070"  # Heller Goldgelb-Bernstein
    elif is_white:
        # Unterscheide Weißwein-Töne
        if any(k in t for k in ["grüngelb", "grünliche reflexe", "sauvignon"]):
            base_color = "#E8EDB3"  # Grüngelb
        elif any(k in t for k in ["strohgelb", "weißburgunder", "pinot grigio"]):
            base_color = "#F0E6B8"  # Strohgelb
        else:
            base_color = "#F6F2AF"  # Standard Zitronengelb
    else:
        # Fallback: Weißwein
        base_color = "#F6F2AF"

    # einfache Scores je Dimension
    acidity = _score(t, ["frisch", "säure", "frische", "zitrus", "lime", "limette", "knackig", "rassig"])
    body = _score(t, ["voll", "kräftig", "opulent", "cremig", "dicht", "schmelz", "struktur"])
    tannin = _score(t, ["tannin", "gerbstoff", "griffig", "feinkörnig", "adstringierend", "gerbstoffe"])
    depth = _score(t, ["komplex", "tiefe", "vielschichtig", "lang", "nachhall", "intensiv"])

    # Süße: Hinweise auf restsüß, lieblich, honig, edelsüß etc.
    sweetness = _score(t, ["lieblich", "süß", "süss", "edelsüß", "spätlese", "beerenauslese", "eiswein", "honig"])
    
    # Restzucker in g/L schätzen basierend auf Stilbezeichnungen
    residual_sugar = 0.0
    if any(k in t for k in ["trockenbeerenauslese", "tba"]):
        residual_sugar = 300.0  # Sehr edelsüß
    elif any(k in t for k in ["beerenauslese", "eiswein"]):
        residual_sugar = 180.0  # Edelsüß
    elif any(k in t for k in ["auslese"]):
        residual_sugar = 80.0  # Süß
    elif any(k in t for k in ["spätlese"]):
        residual_sugar = 40.0  # Medium-süß (kann auch trocken sein)
    elif any(k in t for k in ["lieblich", "feinherb", "restsüß", "restzucker"]):
        residual_sugar = 25.0  # Halbtrocken bis lieblich
    elif any(k in t for k in ["halbtrocken", "off-dry"]):
        residual_sugar = 12.0  # Halbtrocken
    elif any(k in t for k in ["trocken", "dry", "brut"]):
        residual_sugar = 4.0  # Trocken
    else:
        # Default: leicht trocken
        residual_sugar = 6.0

    # Holz / Ausbau
    oak_intensity = 0.0
    oak_style: str | None = None
    if any(k in t for k in ["barrique", "holzfass", "eichenfass", "fassausbau", "oak"]):
        oak_intensity = 0.7
        oak_style = "barrel"
    if any(k in t for k in ["stahltank", "edelstahl", "stainless steel"]):
        oak_style = "steel"
        oak_intensity = max(oak_intensity, 0.2)
    if "orange wine" in t or "orange-wine" in t:
        oak_style = "orange"
        oak_intensity = max(oak_intensity, 0.5)

    # Perlage / Spritzigkeit
    effervescence = 0.0
    if any(k in t for k in ["champagner", "champagne"]):
        effervescence = 1.0
    elif any(k in t for k in ["schaumwein", "sekt", "crémant", "cava", "sparkling", "perlage"]):
        effervescence = 0.8
    elif any(k in t for k in ["perlwein", "frizzante", "prosecco", "petillant"]):
        effervescence = 0.5
    elif any(k in t for k in ["leicht perlend", "spritzig", "prickelnd"]):
        effervescence = 0.3

    # Mineralik / Reifearomen
    mineral_intensity = _score(t, ["mineral", "mineralisch", "schiefer", "kreide", "steinig", "salzig"])
    age_aromas_intensity = _score(t, ["leder", "tabak", "trüffel", "petrol", "petroleum", "reifenoten", "gereift"])

    # Frucht-Clustern für die Ringe 6–10
    citrus_words = ["zitrus", "zitrone", "limette", "grapefruit", "lime"]
    stone_words = ["pfirsich", "aprikose", "nektarine", "marille"]
    tropical_words = ["ananas", "mango", "maracuja", "passionsfrucht", "lychee", "litschi"]
    red_words = ["erdbeere", "himbeere", "kirsche", "rote beeren", "strawberry", "raspberry", "cherry"]
    dark_words = ["blaubeere", "heidelbeere", "brombeere", "schwarze johannisbeere", "pflaume", "plum", "blackberry"]

    def _intensity(words: list[str]) -> float:
        return _score(t, words)

    fruit_citrus = _intensity(citrus_words)
    fruit_stone = _intensity(stone_words)
    fruit_tropical = _intensity(tropical_words)
    fruit_red = _intensity(red_words)
    fruit_dark = _intensity(dark_words)

    # Kräuter/Florales & Würze für Ringe 4 und 5
    herbal_intensity = _score(t, ["gras", "kräuter", "kruter", "heu", "heublume", "minze", "krautig", "blute", "floral", "blume"])
    spice_intensity = _score(t, ["gewrz", "gewrze", "pfeffer", "zimt", "nelke", "muskat", "würzig"])

    # leichte Normalisierung / Basiswerte, angepasst auf imagegen.generate_wine_png
    return {
        "base_color_hex": base_color,
        "wine_type": wine_type,
        "acidity": max(0.2, min(1.0, acidity + 0.1)),
        "body": max(0.2, min(1.0, body + 0.1)),
        "tannin": tannin,
        "depth": max(0.2, depth),
        "sweetness": sweetness,
        "oak_intensity": oak_intensity,
        "oak_style": oak_style,
        "effervescence": effervescence,
        "mineral_intensity": mineral_intensity,
        "age_aromas_intensity": age_aromas_intensity,
        # neue Ring-Intensitäten
        "herbal_intensity": herbal_intensity,
        "spice_intensity": spice_intensity,
        "fruit_citrus": fruit_citrus,
        "fruit_stone": fruit_stone,
        "fruit_tropical": fruit_tropical,
        "fruit_red": fruit_red,
        "fruit_dark": fruit_dark,
        "residual_sugar": residual_sugar,
    }


def run_all_bsp() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(1, 12):
        sub = f"{i:02d}"
        folder = BSP_DIR / sub
        if not folder.is_dir():
            continue

        txt_files = list(folder.glob("*.txt"))
        if not txt_files:
            continue
        txt_path = txt_files[0]

        txt = txt_path.read_text(encoding="utf-8", errors="ignore")
        viz = profile_from_text(txt)

        out = OUT_DIR / f"generated_{sub}.png"
        print(f"[bsp_runner] Generating {out.name} from {txt_path.relative_to(ROOT)}")
        generate_wine_png(viz, size=2048, out_path=str(out))


if __name__ == "__main__":
    run_all_bsp()

from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """
    Input payload für /analyze.
    """
    wine_name: str = Field(..., description='z. B. "Riesling Bürklin-Wolf 2021"')
    use_llm: Optional[bool] = Field(
        default=None,
        description="Aktiviere LLM-Anreicherung (Summaries & strukturierte Daten)",
    )


class SourceItem(BaseModel):
    """
    Ein einzelnes Suchergebnis (Snippet) aus dem Web.
    """
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None  # optional, falls du später scoringen willst


class ColorInfo(BaseModel):
    name: str
    hex: str
    rgb: Tuple[int, int, int]


class WineProps(BaseModel):
    """
    Strukturierte Weineigenschaften.
    """
    vintage: Optional[int] = None
    wine_type: Optional[str] = None  # "red", "white", "rosé", "sparkling"
    variety: Optional[str] = None
    grapes: List[str] = []
    country: Optional[str] = None
    region: Optional[str] = None
    appellation: Optional[str] = None
    producer: Optional[str] = None
    style: Optional[str] = None  # "still", "sparkling", "fortified"
    sweetness: Optional[str] = None  # "dry", "off-dry", ...
    alcohol: Optional[float] = None  # ABV in %
    oak: Optional[bool] = None
    tasting_notes: List[str] = []


class VizProfile(BaseModel):
    """
    Visualisierungsprofil für das Frontend.
    Alle numerischen Felder werden mit clamp() auf [0,1] begrenzt.
    Diese Werte steuern die imagegen.py Visualisierung.
    """
    # Basis-Farbe (wie von oben ins Glas geschaut)
    base_color_hex: Optional[str] = None
    
    # Weintyp für die Visualisierung (bestimmt Farbverlauf-Stil)
    wine_type: str = "auto"  # "red", "white", "rose", "auto"

    # Struktur-Werte 0..1
    acidity: float = 0.5
    body: float = 0.5
    tannin: float = 0.2
    depth: float = 0.4
    sweetness: float = 0.1

    # Aromen-Intensitäten für die Ring-Visualisierung
    oak_intensity: float = 0.0       # Holz/Fass/Toast
    mineral_intensity: float = 0.3   # Mineralik/Feuerstein
    herbal_intensity: float = 0.0    # Kräuter/Gras
    spice_intensity: float = 0.0     # Gewürze/Pfeffer
    
    # Frucht-Intensitäten (bestimmen die Frucht-Ringe)
    fruit_citrus: float = 0.0        # Zitrone, Limette, Grapefruit
    fruit_stone: float = 0.0         # Pfirsich, Aprikose
    fruit_tropical: float = 0.0      # Mango, Ananas, Passionsfrucht
    fruit_red: float = 0.0           # Erdbeere, Himbeere, Kirsche
    fruit_dark: float = 0.0          # Brombeere, Cassis, Pflaume

    # Perlage / Spritzigkeit
    effervescence: float = 0.0       # 0 = still, 0.3-0.5 = Frizzante, 0.7-1.0 = Sekt
    bubbles: bool = False            # True für Schaumwein

    # Legacy-Felder (für Rückwärtskompatibilität)
    oak_style: Optional[str] = None
    bubbles_intensity: float = 0.0
    fruit: List[str] = []
    non_fruit: List[str] = []
    mineral: float = 0.0  # Alias für mineral_intensity
    age_aromas_intensity: float = 0.0
    ripe_aromas: float = 0.0

    def clamp(self) -> None:
        def c(v: float) -> float:
            return max(0.0, min(1.0, float(v)))

        self.acidity = c(self.acidity)
        self.body = c(self.body)
        self.tannin = c(self.tannin)
        self.depth = c(self.depth)
        self.sweetness = c(self.sweetness)
        self.oak_intensity = c(self.oak_intensity)
        self.mineral_intensity = c(self.mineral_intensity)
        self.herbal_intensity = c(self.herbal_intensity)
        self.spice_intensity = c(self.spice_intensity)
        self.fruit_citrus = c(self.fruit_citrus)
        self.fruit_stone = c(self.fruit_stone)
        self.fruit_tropical = c(self.fruit_tropical)
        self.fruit_red = c(self.fruit_red)
        self.fruit_dark = c(self.fruit_dark)
        self.effervescence = c(self.effervescence)
        self.bubbles_intensity = c(self.bubbles_intensity)
        self.age_aromas_intensity = c(self.age_aromas_intensity)
        
        # Sync legacy fields
        if self.mineral > 0 and self.mineral_intensity == 0:
            self.mineral_intensity = c(self.mineral)
        if self.bubbles_intensity > 0 and self.effervescence == 0:
            self.effervescence = c(self.bubbles_intensity)
        if self.bubbles and self.effervescence == 0:
            self.effervescence = 0.7


class CriticSummary(BaseModel):
    """
    Zusammenfassung einer bestimmten Quelle (Winzer / Kritiker / Magazin).
    """
    source_id: str
    source_label: str
    url: Optional[str] = None
    summary: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """
    Haupt-Response für /analyze.
    """
    wine_name: str
    searched_query: str
    engine: str
    tried_queries: List[str] = []
    found: bool
    props: WineProps
    sources: List[SourceItem] = []
    notes: List[str] = []
    used_llm: bool = False
    reasoning: Optional[str] = None
    viz: Optional[VizProfile] = None

    # Kritiker- und Quellen-Summaries
    critic_summaries: List[CriticSummary] = []
    combined_summary: Optional[str] = None

    # Legacy / Frontend-kompatibel
    color: Optional[ColorInfo] = None
    hex: Optional[str] = None
    rgb: Optional[List[int]] = None
    note: Optional[str] = None

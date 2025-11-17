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
    """
    base_color_hex: Optional[str] = None
    acidity: float = 0.4
    body: float = 0.4
    tannin: float = 0.2
    depth: float = 0.4
    sweetness: float = 0.1
    oak: float = 0.1
    bubbles: bool = False
    fruit: List[str] = []
    non_fruit: List[str] = []
    mineral: float = 0.2
    ripe_aromas: float = 0.2

    def clamp(self) -> None:
        def c(v: float) -> float:
            return max(0.0, min(1.0, float(v)))

        self.acidity = c(self.acidity)
        self.body = c(self.body)
        self.tannin = c(self.tannin)
        self.depth = c(self.depth)
        self.sweetness = c(self.sweetness)
        self.oak = c(self.oak)
        self.mineral = c(self.mineral)
        self.ripe_aromas = c(self.ripe_aromas)


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

from typing import List, Optional, Tuple, Any, Dict

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    wine_name: str = Field(..., description='z. B. "Riesling Bürklin-Wolf 2021"')
    use_llm: Optional[bool] = Field(
        default=None,
        description="Aktiviere LLM-Anreicherung (nur fehlende Felder)",
    )


class SourceItem(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None


class ColorInfo(BaseModel):
    name: str
    hex: str
    rgb: Tuple[int, int, int]


class WineProps(BaseModel):
    vintage: Optional[int] = None
    wine_type: Optional[str] = None
    variety: Optional[str] = None
    grapes: List[str] = []
    country: Optional[str] = None
    region: Optional[str] = None
    appellation: Optional[str] = None
    producer: Optional[str] = None
    style: Optional[str] = None
    sweetness: Optional[str] = None
    alcohol: Optional[float] = None
    oak: Optional[bool] = None
    tasting_notes: List[str] = []


class VizProfile(BaseModel):
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


class AnalyzeResponse(BaseModel):
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

    # Legacy
    color: Optional[ColorInfo] = None
    hex: Optional[str] = None
    rgb: Optional[List[int]] = None
    note: Optional[str] = None

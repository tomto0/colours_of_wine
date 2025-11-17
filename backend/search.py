from __future__ import annotations

from typing import Dict, List

from .config import PRIORITY_SOURCES
from .models import SourceItem


async def search_sources_by_priority(wine_name: str) -> Dict[str, List[SourceItem]]:
    """
    Stub-Funktion: Wird aktuell nicht mehr verwendet, weil die Websuche komplett
    über Gemini + Google Search läuft.

    Rückgabe: leeres Mapping pro Quelle.
    """
    return {s["id"]: [] for s in PRIORITY_SOURCES}

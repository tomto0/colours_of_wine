from __future__ import annotations

from typing import Dict, List

import httpx

from .config import PRIORITY_SOURCES, GOOGLE_SEARCH_API_KEY, GOOGLE_CSE_ID, SEARCH_ENABLED
from .models import SourceItem


async def google_search_raw(query: str, num_results: int = 8) -> List[dict]:
    """
    Ruft die Google Custom Search JSON API auf und gibt eine vereinfachte
    Liste von Treffern zurück (title, url, snippet, displayLink).
    """
    if not SEARCH_ENABLED:
        raise RuntimeError("Google Search ist nicht konfiguriert (Key oder CSE ID fehlt).")

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num_results, 10),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"Google Search error {resp.status_code}: {resp.text}")

        data = resp.json()
        items = data.get("items") or []
        results: List[dict] = []
        for item in items:
            results.append(
                {
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "url": item.get("link"),
                    "displayLink": item.get("displayLink"),
                }
            )
        return results


async def search_sources_by_priority(wine_name: str) -> Dict[str, List[SourceItem]]:
    """
    Optionale Hilfsfunktion: erzeugt aktuell nur ein leeres Mapping
    pro priorisierter Quelle. Kann später erweitert werden, um Treffer
    nach Domains aufzuteilen.
    """
    return {s["id"]: [] for s in PRIORITY_SOURCES}

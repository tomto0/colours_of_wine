import re
from typing import List, Optional

from .config import PREFERRED_DOMAINS, DDG_SAFE
from .models import SourceItem

_DDGS_AVAILABLE = False
try:
    import ddgs  # type: ignore
    _DDGS_AVAILABLE = True
except Exception:
    _DDGS_AVAILABLE = False


def _domain_priority(url: str) -> int:
    for i, d in enumerate(PREFERRED_DOMAINS):
        if d in (url or ""):
            return len(PREFERRED_DOMAINS) - i
    return 0


def _normalize_name(name: str) -> tuple[str, str, Optional[str]]:
    name = re.sub(r"\s+", " ", name).strip()
    m = re.search(r"\b(19[6-9]\d|20[0-4]\d)\b", name)
    vintage = m.group(1) if m else None
    base = name
    if vintage:
        base = re.sub(re.escape(vintage), "", name).strip()
    base = re.sub(r"\b(wein|wine)\b", "", base, flags=re.I).strip()
    return name, base, vintage


async def _ddg_text(query: str, region: str, max_results: int = 12) -> List[SourceItem]:
    if not _DDGS_AVAILABLE:
        print("[ddg] ddgs nicht installiert -> keine Quellen.")
        return []

    from ddgs import DDGS  # type: ignore

    res: List[SourceItem] = []
    try:
        with DDGS() as ddg:
            print(f"[ddg] {region} :: {query}")
            for r in ddg.text(query, region=region, safesearch=DDG_SAFE, max_results=max_results):
                title = r.get("title")
                url = r.get("href") or r.get("url")
                snippet = r.get("body")
                if url and title:
                    res.append(SourceItem(title=title, url=url, snippet=snippet))
    except Exception as e:
        print(f"[ddg] Fehler ({region}): {e}")
    return res


def _dedup_sources(items: List[SourceItem]) -> List[SourceItem]:
    seen = set()
    out: List[SourceItem] = []
    for s in items:
        key = (s.url or "").split("?")[0]
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _score_source(s: SourceItem, base: str, vintage: Optional[str]) -> float:
    t = f"{s.title or ''} {s.snippet or ''}".lower()
    base_l = base.lower()
    score = 0.0

    if base_l and base_l in t:
        score += 5.0

    tokens = [w for w in re.split(r"[^\wäöüÄÖÜß]+", base_l) if w]
    score += sum(0.8 for w in tokens if w in t)

    if vintage and vintage in t:
        score += 1.5

    score += 0.3 * _domain_priority(s.url or "")
    return score


def _rank_and_filter(items: List[SourceItem], wine_name: str) -> List[SourceItem]:
    full, base, vintage = _normalize_name(wine_name)

    filtered: List[SourceItem] = []
    for s in items:
        txt = f"{s.title or ''} {s.snippet or ''}".lower()
        if any(w for w in base.lower().split() if w and w in txt) or (vintage and vintage in txt):
            s.score = _score_source(s, base, vintage)
            filtered.append(s)
    filtered.sort(key=lambda x: x.score or 0.0, reverse=True)
    return filtered[:10]

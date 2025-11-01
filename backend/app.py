from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import os, glob, re

app = FastAPI()

# CORS für Entwicklung: alle Origins erlauben (später einschränken!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeIn(BaseModel):
    wine_name: str

FACTORS = [
    ("complexity", "Komplexität"),
    ("acidity", "Säure"),
    ("tannin", "Tannin"),
    ("body", "Körper"),
    ("fruit", "Frucht"),
    ("oak", "Holz"),
    ("mineral", "Mineralik"),
    ("length", "Länge"),
    ("balance", "Balance"),
]

@app.get("/health")
def health():
    return {"ok": True}

def read_corpus(name_query: str, corpus_dir: str = "corpus") -> str:
    if not os.path.isdir(corpus_dir):
        return ""
    files = glob.glob(os.path.join(corpus_dir, "**", "*.txt"), recursive=True)
    hits = []
    for f in files:
        try:
            t = open(f, "r", encoding="utf-8", errors="ignore").read()
            if name_query.lower() in t.lower():
                hits.append(t)
        except Exception:
            pass
    if not hits:  # Fallback: nimm ein paar Dateien
        for f in files[:10]:
            try:
                hits.append(open(f, "r", encoding="utf-8", errors="ignore").read())
            except:
                pass
    return "\n\n---\n\n".join(hits)

def heuristic_values(text: str) -> Dict[str, float]:
    def score(wordset: str, base: float = 0.55):
        return base
    return {
        "complexity": 0.7,
        "acidity": 0.65,
        "tannin": 0.6,
        "body": 0.65,
        "fruit": 0.6,
        "oak": 0.55,
        "mineral": 0.55,
        "length": 0.65,
        "balance": 0.6,
    }

@app.post("/analyze")
def analyze(inp: AnalyzeIn):
    name = inp.wine_name.strip()
    if not name:
        raise HTTPException(400, "wine_name required")

    ctx = read_corpus(name)  # optional, kann leer sein
    vals = heuristic_values(ctx)

    factors = [{"key": k, "label": lbl, "value": float(max(0, min(1, vals[k])))} for k, lbl in FACTORS]

    return {
        "title": name,
        "summary": f"{name} – automatische Einschätzung (Fallback).",
        "description": "LLM/RAG noch nicht aktiv – heuristische Werte. (Später durch echten LLM-Call ersetzen.)",
        "sources": [],
        "factors": factors,
        "styleHints": {"palette": "warm_red" if "pinot" not in name.lower() else "cool_green"}
    }

"""
SQLite-basierter Cache für Weinanalysen.
Speichert viz_profile und combined_summary für bereits analysierte Weine.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Datenbank-Pfad (im backend Ordner)
DB_PATH = Path(__file__).parent / "wine_cache.db"


def _get_connection() -> sqlite3.Connection:
    """Erstellt eine Verbindung zur SQLite-Datenbank."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialisiert die Datenbank und erstellt die Tabelle falls nötig."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wine_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wine_name TEXT NOT NULL,
            wine_name_normalized TEXT NOT NULL UNIQUE,
            viz_profile TEXT,
            combined_summary TEXT,
            props TEXT,
            hex_color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Index für schnelle Suche
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wine_name_normalized 
        ON wine_cache(wine_name_normalized)
    """)
    
    conn.commit()
    conn.close()


def _normalize_name(wine_name: str) -> str:
    """
    Normalisiert den Weinnamen für konsistente Suche.
    - Lowercase
    - Mehrfache Leerzeichen entfernen
    - Trimmen
    """
    return " ".join(wine_name.lower().strip().split())


def get_cached_wine(wine_name: str) -> Optional[dict]:
    """
    Sucht einen Wein im Cache.
    
    Returns:
        dict mit viz_profile, combined_summary, props, hex wenn gefunden,
        None wenn nicht im Cache.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    normalized = _normalize_name(wine_name)
    
    cursor.execute("""
        SELECT viz_profile, combined_summary, props, hex_color, wine_name, created_at
        FROM wine_cache 
        WHERE wine_name_normalized = ?
    """, (normalized,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        return None
    
    result = {
        "wine_name": row["wine_name"],
        "hex": row["hex_color"],
        "created_at": row["created_at"],
    }
    
    # JSON-Felder parsen
    if row["viz_profile"]:
        try:
            result["viz"] = json.loads(row["viz_profile"])
        except json.JSONDecodeError:
            result["viz"] = None
    
    if row["combined_summary"]:
        result["combined_summary"] = row["combined_summary"]
    
    if row["props"]:
        try:
            result["props"] = json.loads(row["props"])
        except json.JSONDecodeError:
            result["props"] = {}
    
    return result


def save_to_cache(
    wine_name: str,
    viz_profile: Optional[dict] = None,
    combined_summary: Optional[str] = None,
    props: Optional[dict] = None,
    hex_color: Optional[str] = None,
) -> None:
    """
    Speichert einen Wein im Cache.
    Bei existierendem Eintrag wird dieser aktualisiert.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    
    normalized = _normalize_name(wine_name)
    now = datetime.now().isoformat()
    
    # JSON serialisieren
    viz_json = json.dumps(viz_profile) if viz_profile else None
    props_json = json.dumps(props) if props else None
    
    # Upsert (INSERT or UPDATE)
    cursor.execute("""
        INSERT INTO wine_cache (
            wine_name, wine_name_normalized, viz_profile, 
            combined_summary, props, hex_color, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(wine_name_normalized) DO UPDATE SET
            viz_profile = excluded.viz_profile,
            combined_summary = excluded.combined_summary,
            props = excluded.props,
            hex_color = excluded.hex_color,
            updated_at = excluded.updated_at
    """, (
        wine_name, normalized, viz_json, 
        combined_summary, props_json, hex_color, now, now
    ))
    
    conn.commit()
    conn.close()


def get_cache_stats() -> dict:
    """Gibt Statistiken über den Cache zurück."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM wine_cache")
    count = cursor.fetchone()["count"]
    
    cursor.execute("""
        SELECT wine_name, created_at 
        FROM wine_cache 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    recent = [{"name": row["wine_name"], "date": row["created_at"]} for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "total_entries": count,
        "recent_entries": recent,
    }


def clear_cache() -> int:
    """Löscht alle Einträge im Cache. Gibt Anzahl gelöschter Einträge zurück."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM wine_cache")
    count = cursor.fetchone()["count"]
    
    cursor.execute("DELETE FROM wine_cache")
    conn.commit()
    conn.close()
    
    return count


# Datenbank beim Import initialisieren
init_db()

"""SQLite-Zugriff. Bewusst ohne ORM - das Schema ist klein genug."""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("KCAL_DB", "/data/kcal.db"))
SCHEMA = Path(__file__).with_name("schema.sql")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init() -> None:
    with connect() as con:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))


def get_setting(con, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(con, key: str, value: str) -> None:
    con.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


# ---------------------------------------------------------------
# Plausibilitaet
# ---------------------------------------------------------------
def is_suspect(kcal_100, protein_100, carbs_100, fat_100) -> bool:
    """Open Food Facts ist crowdsourced. Haeufigster Fehler: kJ im kcal-Feld
    (Faktor ~4,2 zu hoch). Zweiter Test: rechnen sich die Makros zur
    angegebenen Energie zusammen?"""
    kcal = float(kcal_100 or 0)
    if kcal <= 0 or kcal > 900:          # reines Fett liegt bei ~900
        return True
    p, c, f = float(protein_100 or 0), float(carbs_100 or 0), float(fat_100 or 0)
    if p + c + f > 105:                  # mehr als 100 g pro 100 g
        return True
    if p or c or f:
        calc = p * 4 + c * 4 + f * 9
        if calc > 0 and abs(calc - kcal) / kcal > 0.25:
            return True
    return False


def scale(food: sqlite3.Row, grams: float) -> dict:
    """Naehrwerte je 100 g auf die tatsaechliche Menge umrechnen."""
    factor = grams / 100.0
    return {
        "kcal": round((food["kcal_100"] or 0) * factor, 1),
        "protein": round((food["protein_100"] or 0) * factor, 1),
        "carbs": round((food["carbs_100"] or 0) * factor, 1),
        "fat": round((food["fat_100"] or 0) * factor, 1),
    }

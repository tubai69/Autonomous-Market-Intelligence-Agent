import sqlite3
from pathlib import Path
from typing import Optional

from app.config import settings
from app.schemas import Report


def _conn() -> sqlite3.Connection:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, payload TEXT)")
    return conn


def save_report(report: Report) -> Report:
    conn = _conn()
    with conn:
        cur = conn.execute("INSERT INTO reports (created_at, payload) VALUES (?, ?)",
                           (report.created_at.isoformat(), report.model_dump_json()))
        report.id = cur.lastrowid
    conn.close()
    return report


def _load(row) -> Report:
    r = Report.model_validate_json(row[1])
    r.id = row[0]
    return r


def latest_report() -> Optional[Report]:
    conn = _conn()
    row = conn.execute("SELECT id, payload FROM reports ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return _load(row) if row else None


def list_reports(limit: int = 10) -> list[Report]:
    conn = _conn()
    rows = conn.execute("SELECT id, payload FROM reports ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [_load(r) for r in rows]

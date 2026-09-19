import sqlite3
from pathlib import Path
from app.models import Inscription

class Repository:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "ancientlens.sqlite3"
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS inscriptions (id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    def connect(self):
        return sqlite3.connect(self.path)
    def save(self, result: Inscription):
        with self.connect() as conn:
            conn.execute("INSERT INTO inscriptions(id,schema_version,result_json) VALUES (?,?,?)", (result.id, result.schema_version, result.model_dump_json()))
    def get(self, id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT result_json FROM inscriptions WHERE id=?", (id,)).fetchone()
        return Inscription.model_validate_json(row[0]) if row else None

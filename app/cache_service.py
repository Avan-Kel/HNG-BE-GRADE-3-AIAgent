# app/cache_service.py
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional


class SQLiteCache:
    def __init__(self, db_path: str, ttl_days: int = 14):
        self.db_path = db_path
        self.ttl = timedelta(days=ttl_days)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                payload TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    def get(self, key: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT payload, updated_at FROM cache WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()

        if not row:
            return None

        payload, updated_at = row
        updated_at = datetime.fromisoformat(updated_at)

        # expired
        if datetime.utcnow() - updated_at > self.ttl:
            return None

        return json.loads(payload)

    def set(self, key: str, payload: dict):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO cache (key, payload, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload), datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

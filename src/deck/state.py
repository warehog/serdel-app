from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import sqlite3
import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  service TEXT,
  command TEXT,
  mode TEXT,
  payload TEXT
);
"""


@dataclass
class State:
    dsn: str
    _conn: Optional[sqlite3.Connection] = None

    def open(self) -> None:
        self._conn = sqlite3.connect(self.dsn)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def event(self, service: str | None, command: str, mode: str, payload: dict | None = None) -> None:
        assert self._conn is not None, "state not opened"
        self._conn.execute(
            "INSERT INTO events(ts, service, command, mode, payload) VALUES(?,?,?,?,?)",
            (datetime.utcnow().isoformat(), service, command, mode, json.dumps(payload or {})),
        )
        self._conn.commit()
"""Small SQLite persistence layer with explicit transactions."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    endpoint TEXT NOT NULL,
    listen_port INTEGER NOT NULL,
    subnet TEXT NOT NULL,
    dns TEXT NOT NULL,
    client_allowed_ips TEXT NOT NULL,
    mtu INTEGER,
    server_private_key TEXT NOT NULL,
    server_public_key TEXT NOT NULL,
    admin_password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS peers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    address TEXT NOT NULL UNIQUE,
    private_key TEXT NOT NULL,
    public_key TEXT NOT NULL UNIQUE,
    preshared_key TEXT NOT NULL,
    client_allowed_ips TEXT NOT NULL,
    dns TEXT NOT NULL,
    persistent_keepalive INTEGER NOT NULL DEFAULT 25,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(self.connect()) as conn:
            conn.executescript(SCHEMA)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def setting(self) -> sqlite3.Row | None:
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM settings WHERE id=1").fetchone()

    def peers(self) -> list[sqlite3.Row]:
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM peers ORDER BY name COLLATE NOCASE").fetchall()

    def peer(self, peer_id: str) -> sqlite3.Row | None:
        with closing(self.connect()) as conn:
            return conn.execute("SELECT * FROM peers WHERE id=?", (peer_id,)).fetchone()

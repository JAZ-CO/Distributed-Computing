# persistence.py
# ---------------------------------------------
# Lightweight, thread-safe SQLite message store
# for logging chat messages (in/out), replaying
# recent history on join, and simple text search.
# ---------------------------------------------

from __future__ import annotations
import sqlite3, time, threading
from pathlib import Path
from typing import List, Tuple, Optional

# Schema: single messages table + helpful indexes
_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,                  -- unix timestamp (float)
  direction TEXT CHECK(direction IN ('in','out')) NOT NULL,
  from_user TEXT NOT NULL,           -- sender username
  first_name TEXT,
  last_name  TEXT,
  grp TEXT NOT NULL,                 -- chat group/partition
  text TEXT NOT NULL                 -- message body
);
CREATE INDEX IF NOT EXISTS idx_messages_grp_ts ON messages(grp, ts);
CREATE INDEX IF NOT EXISTS idx_messages_text   ON messages(text);
"""

class MessageStore:
    """Small wrapper around sqlite3 with a lock for safe multi-thread use."""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self._lock = threading.Lock()
        # check_same_thread=False lets other threads reuse this connection
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def save(
        self,
        *,
        direction: str,          # 'in' or 'out'
        from_user: str,
        first_name: str,
        last_name: str,
        grp: str,
        text: str,
        ts: Optional[float] = None
    ) -> None:
        """Insert a single message row."""
        if ts is None:
            ts = time.time()
        with self._lock, self._conn:  # atomic write
            self._conn.execute(
                "INSERT INTO messages(ts,direction,from_user,first_name,last_name,grp,text) "
                "VALUES(?,?,?,?,?,?,?)",
                (ts, direction, from_user, first_name, last_name, grp, text),
            )

    def recent(self, grp: str, limit: int = 100) -> List[Tuple[float,str,str,str,str,str]]:
        """
        Return last `limit` messages for a group, oldest→newest.
        Row tuple: (ts, direction, from_user, first_name, last_name, text)
        """
        cur = self._conn.cursor()
        cur.execute(
            "SELECT ts,direction,from_user,first_name,last_name,text "
            "FROM messages WHERE grp=? ORDER BY ts DESC LIMIT ?",
            (grp, limit),
        )
        rows = cur.fetchall()
        rows.reverse()  # we queried DESC; show in chronological order
        return rows

    def search(self, grp: str, query: str, limit: int = 100) -> List[Tuple[float,str,str,str,str,str]]:
        """
        LIKE-based search over `text` for a group, oldest→newest.
        (Good enough for class; swap to FTS5 if you want full-text search.)
        """
        cur = self._conn.cursor()
        cur.execute(
            "SELECT ts,direction,from_user,first_name,last_name,text "
            "FROM messages WHERE grp=? AND text LIKE ? ORDER BY ts DESC LIMIT ?",
            (grp, f"%{query}%", limit),
        )
        rows = cur.fetchall()
        rows.reverse()
        return rows

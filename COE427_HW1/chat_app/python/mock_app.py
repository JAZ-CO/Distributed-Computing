# mock_app.py
"""
Lightweight local backend to mimic publish/subscribe + history
without RTI. Uses UDP multicast so multiple app instances can chat.

Public API (kept for compatibility with app/app_no_rti):
- DDSApp(username, room, on_message, db_path="chat.db")
- start()
- publish(text)   # text is a JSON string produced by the GUI layer
- get_history(limit=200) -> list[dict]
- close()
"""

import json
import socket
import sqlite3
import struct
import threading
import time
from typing import Optional

MCAST_GRP = "239.255.0.1"
MCAST_PORT = 49600
ENC = "utf-8"

_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  direction TEXT NOT NULL,           -- 'in' or 'out'
  from_user TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  grp TEXT NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_messages_grp_ts ON messages(grp, ts);
"""

class DDSApp:
    def __init__(self, username: str, room: str, on_message=None, db_path: str = "chat.db"):
        self.username = username
        self.room = room
        self.on_message = on_message
        self.db_path = db_path

        self._sock: Optional[socket.socket] = None
        self._rx_th: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # DB connection for this instance (thread safe for simple use)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.executescript(_SQL_SCHEMA)
        self.db.commit()

    # ---- network helpers ----

    def _make_sock(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", MCAST_PORT))  # Windows: bind INADDR_ANY for multicast receive
        except OSError:
            pass
        mreq = struct.pack("=4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError:
            pass
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        except OSError:
            pass
        return s

    # ---- lifecycle ----

    def start(self):
        if not self._sock:
            self._sock = self._make_sock()
        if not self._rx_th:
            self._rx_th = threading.Thread(target=self._rx_loop, daemon=True)
            self._rx_th.start()

    def close(self):
        self._stop.set()
        try:
            if self._sock:
                mreq = struct.pack("=4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
                try:
                    self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                except OSError:
                    pass
                self._sock.close()
        finally:
            try:
                self.db.close()
            except Exception:
                pass

    # ---- storage ----

    def _store(self, *, direction: str, from_user: str, text: str, first_name: str = "", last_name: str = "", ts: Optional[float] = None):
        if ts is None:
            ts = time.time()
        self.db.execute(
            "INSERT INTO messages(ts,direction,from_user,first_name,last_name,grp,text) VALUES(?,?,?,?,?,?,?)",
            (ts, direction, from_user, first_name, last_name, self.room, text),
        )
        self.db.commit()

    # ---- IO ----

    def publish(self, text: str):
        """Send a JSON payload to the multicast group and store an 'out' record locally."""
        if not self._sock:
            self._sock = self._make_sock()

        # store locally as 'out' using the correct schema (NO 'username' column)
        try:
            self._store(direction="out", from_user=self.username, text=text)
        except Exception:
            pass

        payload = {
            "room": self.room,
            "username": self.username,
            "text": text,
            "ts": time.time(),
        }
        try:
            data = json.dumps(payload, ensure_ascii=False).encode(ENC, errors="ignore")
        except Exception:
            data = json.dumps({"room": self.room, "username": self.username, "text": str(text), "ts": time.time()}).encode(ENC, errors="ignore")

        try:
            self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        except OSError:
            pass
        self._sock.sendto(data, (MCAST_GRP, MCAST_PORT))

    def _rx_loop(self):
        while not self._stop.is_set():
            try:
                data, _ = self._sock.recvfrom(64 * 1024)
                msg = json.loads(data.decode(ENC, errors="ignore"))
                if msg.get("room") != self.room:
                    continue
                author = msg.get("username", "")
                text = msg.get("text", "")
                ts = msg.get("ts")

                # store as 'in' unless it's our own send
                if author and author != self.username:
                    try:
                        self._store(direction="in", from_user=author, text=text, ts=ts)
                    except Exception:
                        pass

                if self.on_message:
                    self.on_message(msg)
            except Exception:
                continue

    # ---- history ----

    def get_history(self, limit: int = 200):
        """Return last messages for this room as a list of dicts with keys: username,text,ts."""
        try:
            cur = self.db.cursor()
            cur.execute(
                "SELECT ts,direction,from_user,text FROM messages WHERE grp=? ORDER BY ts DESC LIMIT ?",
                (self.room, limit),
            )
            rows = cur.fetchall()
            out = []
            for ts, direction, from_user, text in rows:
                out.append({"username": from_user, "text": text, "ts": ts, "direction": direction})
            return out
        except Exception:
            return []

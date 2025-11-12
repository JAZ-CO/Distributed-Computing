# app_no_rti.py
import json
import sqlite3
import gui
import mock_app
from persistence import MessageStore
from typing import List, Dict, Optional, Tuple

PRESENCE_JOIN = {"_type": "presence", "action": "join"}
PRESENCE_LEAVE = {"_type": "presence", "action": "leave"}

def _parse_payload(text: str):
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return None

class MainAppNoRTI:
    """
    Same GUI behavior as the RTI version, but uses mock_app (UDP multicast + SQLite).
    """
    def __init__(self, db_path: str = "chat.db"):
        self.gui_handlers = gui.Handlers()
        self.gui_handlers.join = self.join
        self.gui_handlers.update_user = self.update_user
        self.gui_handlers.leave = self.leave
        self.gui_handlers.list_users = self.list_users
        self.gui_handlers.send_message = self.send
        self.gui = gui.GuiApp(self.gui_handlers)

        self.store: Optional[MessageStore] = None
        self.backend: Optional[mock_app.DDSApp] = None
        self.user: Optional[str] = None
        self.group: Optional[str] = None
        self.first_name: str = ""
        self.last_name: str = ""
        self.db_path = db_path
        self._online: Dict[str, Dict[str, str]] = {}

        self.gui.start()
        self.leave()

    # ---------------- GUI handler implementations ----------------

    def join(self, user: str, group: str, first_name: str, last_name: str):
        self.user = user
        self.group = group
        self.first_name = first_name or ""
        self.last_name = last_name or ""

        self.store = MessageStore(self.db_path)
        self.backend = mock_app.DDSApp(username=user, room=group, on_message=self._on_message, db_path=self.db_path)
        self.backend.start()

        # replay history (oldest → newest), skip presence, dedup obvious repeats
        seen: set[Tuple[str, str, str]] = set()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT ts, direction, from_user, text FROM messages "
                    "WHERE grp=? ORDER BY ts DESC LIMIT 200",
                    (group,),
                )
                rows = cur.fetchall()
                rows.reverse()
                for ts, direction, author, text in rows:
                    key = (author or "?", str(int(ts)), text or "")
                    if key in seen:
                        continue
                    seen.add(key)

                    obj = _parse_payload(text)
                    if obj and obj.get("_type") == "presence":
                        continue
                    if obj and obj.get("_type") == "chat":
                        msg_txt = obj.get("text", "")
                        dest = obj.get("to", group)
                        if dest == group or dest == (self.user or ""):
                            self.gui.message_received(obj.get("from", author or "?"), dest, msg_txt)
                        continue
                    self.gui.message_received(author or "?", group, text)
        except Exception:
            pass

        # presence announce + add self
        self._publish_control(PRESENCE_JOIN)
        self._online[self.user] = {"first_name": self.first_name, "last_name": self.last_name}
        self.gui.user_joined(self.user, self.group, self.first_name, self.last_name)

    def update_user(self, new_group: str):
        if not self.backend or not self.user:
            return
        if new_group == self.group:
            return

        self._publish_control(PRESENCE_LEAVE)
        self.backend.close()
        self._online.clear()

        self.group = new_group
        self.backend = mock_app.DDSApp(username=self.user, room=self.group, on_message=self._on_message, db_path=self.db_path)
        self.backend.start()

        seen: set[Tuple[str, str, str]] = set()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT ts, direction, from_user, text FROM messages "
                    "WHERE grp=? ORDER BY ts DESC LIMIT 200",
                    (self.group,),
                )
                rows = cur.fetchall()
                rows.reverse()
                for ts, direction, author, text in rows:
                    key = (author or "?", str(int(ts)), text or "")
                    if key in seen:
                        continue
                    seen.add(key)

                    obj = _parse_payload(text)
                    if obj and obj.get("_type") == "presence":
                        continue
                    if obj and obj.get("_type") == "chat":
                        msg_txt = obj.get("text", "")
                        dest = obj.get("to", self.group)
                        if dest == self.group or dest == (self.user or ""):
                            self.gui.message_received(obj.get("from", author or "?"), dest, msg_txt)
                        continue
                    self.gui.message_received(author or "?", self.group, text)
        except Exception:
            pass

        self._publish_control(PRESENCE_JOIN)

    def leave(self):
        try:
            if self.backend:
                self._publish_control(PRESENCE_LEAVE)
        except Exception:
            pass
        try:
            if self.backend:
                self.backend.close()
        finally:
            self.backend = None
            self._online.clear()

    def list_users(self) -> List[List[str]]:
        return [[u, self.group or "", v.get("first_name", ""), v.get("last_name", "")] for u, v in sorted(self._online.items())]

    def send(self, destination: str, message: str):
        if not self.backend or not message:
            return
        payload = {"_type": "chat", "from": self.user, "to": destination, "group": self.group, "text": message}
        self.backend.publish(json.dumps(payload, ensure_ascii=False))
        # IMPORTANT: don't save here; backend is the single writer

    # ---------------- backend callback ----------------

    def _on_message(self, msg: dict):
        text = msg.get("text", "")
        obj = _parse_payload(text)
        if obj and obj.get("_type") == "presence":
            author = msg.get("username", "?")
            act = obj.get("action")
            if act == "join":
                if author not in self._online:
                    fn = obj.get("first_name", "")
                    ln = obj.get("last_name", "")
                    self._online[author] = {"first_name": fn, "last_name": ln}
                    if author != (self.user or ""):
                        self.gui.user_joined(author, self.group or "", fn, ln)
            elif act == "leave":
                if author in self._online and author != (self.user or ""):
                    self.gui.user_left(author)
                    self._online.pop(author, None)
            return

        if obj and obj.get("_type") == "chat":
            author = obj.get("from", "?")
            to = obj.get("to", self.group or "")
            txt = obj.get("text", "")
            if to == self.group or to == (self.user or ""):
                self.gui.message_received(author, to, txt)
            return

        # Fallback (non-JSON)
        self.gui.message_received(msg.get("username", "?"), self.group or "", text)

    # ---------------- helpers ----------------

    def _publish_control(self, payload: dict):
        if not self.backend:
            return
        enriched = dict(payload)
        enriched["first_name"] = self.first_name
        enriched["last_name"] = self.last_name
        self.backend.publish(json.dumps(enriched, ensure_ascii=False))

def main():
    return MainAppNoRTI()

if __name__ == "__main__":
    main()

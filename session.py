"""
Session Manager — conversation rooms for agent group chat.
"""

import json
import time
import uuid
import queue
import threading
from pathlib import Path


class SessionManager:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions = {}  # sid -> Session
        self._lock = threading.Lock()

    def create(self, topic: str) -> str:
        sid = f"ws_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        session = Session(sid, topic)
        with self._lock:
            self._sessions[sid] = session
        return sid

    def add_message(self, sid: str, role: str, content: str):
        with self._lock:
            s = self._sessions.get(sid)
            if s:
                s.add_message(role, content)

    def get_history(self, sid: str) -> list:
        with self._lock:
            s = self._sessions.get(sid)
            return s.history.copy() if s else []

    def get_topic(self, sid: str) -> str:
        with self._lock:
            s = self._sessions.get(sid)
            return s.topic if s else ""

    def subscribe(self, sid: str) -> queue.Queue | None:
        with self._lock:
            s = self._sessions.get(sid)
            if s:
                q = queue.Queue()
                s.subscribers.append(q)
                return q
        return None

    def unsubscribe(self, sid: str, q: queue.Queue):
        with self._lock:
            s = self._sessions.get(sid)
            if s and q in s.subscribers:
                s.subscribers.remove(q)

    def broadcast(self, sid: str, msg: dict):
        msg["timestamp"] = time.time()
        with self._lock:
            s = self._sessions.get(sid)
            if s:
                for q in s.subscribers:
                    try:
                        q.put_nowait(msg)
                    except queue.Full:
                        pass

    def stop(self, sid: str):
        with self._lock:
            s = self._sessions.get(sid)
            if s:
                s.active = False

    def is_active(self, sid: str) -> bool:
        with self._lock:
            s = self._sessions.get(sid)
            return s.active if s else False

    def list_sessions(self) -> list:
        with self._lock:
            return [
                {"id": s.id, "topic": s.topic, "messages": len(s.history), "active": s.active}
                for s in self._sessions.values()
            ]


class Session:
    def __init__(self, id: str, topic: str):
        self.id = id
        self.topic = topic
        self.history = []
        self.subscribers = []
        self.active = True
        self.created_at = time.time()

    def add_message(self, role: str, content: str):
        self.history.append({
            "role": role,
            "content": content,
            "time": time.time()
        })

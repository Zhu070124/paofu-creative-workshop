"""
泡芙的创意工坊 — Agent Group Chat Server (v2)
================================================
WebSocket Hub + HTTP/SSE frontend.

Architecture:
  - WebSocket server: agents connect as clients, workshop routes messages
  - HTTP server: serves UI + SSE stream for browser dashboard
  - Workshop doesn't call agents — agents connect and speak when they want

Protocol (WS JSON):
  Agent → Workshop:
    {"type":"register","name":"puff","token":"WORKSHOP_TOKEN"}
    {"type":"response","content":"..."}
    {"type":"typing","active":true|false}
  Workshop → Agent:
    {"type":"welcome","agents":["puff","hermes"]}
    {"type":"message","from":"user","content":"...","round":1}
    {"type":"message","from":"hermes","content":"...","round":1}
    {"type":"agent_joined","name":"puff"}
    {"type":"agent_left","name":"puff"}
    {"type":"error","code":"AUTH_REQUIRED","message":"..."}


Design note — asyncio + threading hybrid:
  The WebSocket server runs on asyncio (main event loop) for non-blocking I/O.
  The HTTP server runs in a ThreadingHTTPServer (separate thread) because
  http.server is synchronous. A broadcast_queue bridges the two worlds:
  HTTP handlers put() messages, an asyncio background task get()s and fans out.
  This is intentional: migrating HTTP to aiohttp would eliminate the hybrid
  but adds a dependency. The current design works for <50 concurrent agents
  and keeps the dependency count at 1 (websockets).
"""

import os, sys, json, time, asyncio, threading, queue, sqlite3, logging, uuid, hmac, signal
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

import websockets
from websockets.asyncio.server import serve as ws_serve

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE = "workshop.log"

def setup_logging():
    logger = logging.getLogger("workshop")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(ch)

    return logger

logger = setup_logging()

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Paths & Config ───────────────────────────────────────────────────────────
WORKSHOP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = WORKSHOP_DIR / "ui"
DB_PATH = WORKSHOP_DIR / "workshop.db"

WORKSHOP_TOKEN = os.environ.get("WORKSHOP_TOKEN", "paofu-workshop-2026")

# ── Rate Limiting ────────────────────────────────────────────────────────────
MAX_MSG_PER_WINDOW = 10
RATE_WINDOW_SEC = 60
rate_limits: dict[str, list[float]] = {}  # agent_name -> [timestamps]

def check_rate_limit(agent_name: str) -> bool:
    """Returns True if the agent is allowed to send another message."""
    now = time.time()
    if agent_name not in rate_limits:
        rate_limits[agent_name] = []
    # Purge old timestamps outside the window
    rate_limits[agent_name] = [t for t in rate_limits[agent_name] if now - t < RATE_WINDOW_SEC]
    if len(rate_limits[agent_name]) >= MAX_MSG_PER_WINDOW:
        return False
    rate_limits[agent_name].append(now)
    return True

# ── Message Validation ───────────────────────────────────────────────────────
MAX_MESSAGE_LENGTH = 2000

def validate_message(content) -> tuple:
    """Returns (valid: bool, error_message: str|None, http_code: int|None)."""
    if not content:
        return False, "Empty message", 400
    if not isinstance(content, str):
        return False, "Content must be a string", 400
    if len(content) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long (max {MAX_MESSAGE_LENGTH} chars)", 413
    return True, None, None

# ── SQLite Persistence ───────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized: {DB_PATH}")

def save_message(session_id: str, role: str, content: str):
    """Persist a chat message to SQLite."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save message: {e}")

def get_history(session_id: str = None, limit: int = 200) -> list[dict]:
    """Retrieve chat history from SQLite."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        if session_id:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT role, content FROM messages ORDER BY id ASC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return []

# ── Session State ────────────────────────────────────────────────────────────
class Session:
    def __init__(self, topic: str):
        self.id = uuid.uuid4().hex[:12]
        self.topic = topic
        self.history: list[dict] = []
        self.subscribers: list[queue.Queue] = []
        self.active = True
        self.round = 0
        self.responses_this_round: list[str] = []

session: Session | None = None
connected_agents: dict[str, any] = {}  # name -> ws
state_lock = threading.Lock()
broadcast_queue: queue.Queue = queue.Queue()

def broadcast_to_frontend(msg: dict):
    msg["ts"] = time.time()
    with state_lock:
        if not session:
            return
        dead = []
        for q in session.subscribers:
            try:
                q.put_nowait(msg)
            except:
                dead.append(q)
        for q in dead:
            session.subscribers.remove(q)

async def broadcast_to_agents(msg: dict):
    with state_lock:
        dead = []
        for name, ws in list(connected_agents.items()):
            try:
                await ws.send(json.dumps(msg, ensure_ascii=False))
            except:
                dead.append(name)
        for name in dead:
            del connected_agents[name]
            broadcast_to_frontend({"type":"agent_left","agent":name})
            logger.info(f"Agent '{name}' removed (dead connection)")

# ── WebSocket: Agent connections ───────────────────────────────────────────
async def handle_agent(ws):
    agent_name = None
    authenticated = False
    try:
        async for raw in ws:
            # Validate JSON structure
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send(json.dumps({"type":"error","code":"INVALID_JSON","message":"Invalid JSON format"}))
                continue

            if not isinstance(data, dict):
                await ws.send(json.dumps({"type":"error","code":"INVALID_FORMAT","message":"Message must be a JSON object"}))
                continue

            msg_type = data.get("type", "")

            # ── Registration (with token auth) ──────────────────────────────
            if msg_type == "register":
                token = data.get("token", "")
                if not hmac.compare_digest(str(token), WORKSHOP_TOKEN):
                    logger.warning(f"Auth failed: invalid token from agent trying to register as '{data.get('name','?')}'")
                    await ws.send(json.dumps({"type":"error","code":"AUTH_REQUIRED","message":"Invalid or missing authentication token"}))
                    await ws.close(4001, "Authentication required")
                    return

                agent_name = data.get("name", "")
                if not isinstance(agent_name, str) or not agent_name.strip():
                    await ws.send(json.dumps({"type":"error","code":"INVALID_NAME","message":"Agent name is required"}))
                    continue

                authenticated = True
                with state_lock:
                    connected_agents[agent_name] = ws
                await ws.send(json.dumps({"type":"welcome","topic":session.topic if session else ""},
                    ensure_ascii=False))
                broadcast_to_frontend({"type":"agent_joined","agent":agent_name})
                # Send existing session history to new agent
                with state_lock:
                    if session and session.history:
                        await ws.send(json.dumps({"type":"history","messages":session.history},
                            ensure_ascii=False))
                logger.info(f"Agent '{agent_name}' connected and authenticated")

            # ── All other messages require authentication ───────────────────
            elif not authenticated:
                await ws.send(json.dumps({"type":"error","code":"NOT_REGISTERED","message":"You must register first"}))
                continue

            elif msg_type == "response":
                content = data.get("content", "")
                valid, err_msg, err_code = validate_message(content)
                if not valid:
                    await ws.send(json.dumps({"type":"error","code":"VALIDATION_ERROR","message":err_msg}))
                    logger.warning(f"Message validation failed for '{agent_name}': {err_msg}")
                    continue

                if not check_rate_limit(agent_name):
                    await ws.send(json.dumps({"type":"error","code":"RATE_LIMITED","message":"Rate limit exceeded (10 msg/60s)"}))
                    logger.warning(f"Rate limit hit for '{agent_name}'")
                    continue

                with state_lock:
                    if session:
                        session.history.append({"role": agent_name, "content": content})
                        session.responses_this_round.append(agent_name)
                        sid = session.id
                        rnd = session.round
                    else:
                        sid = "no-session"
                        rnd = 0

                save_message(sid, agent_name, content)

                broadcast_to_frontend({
                    "type": "agent_message", "agent": agent_name,
                    "content": content, "round": rnd
                })
                await broadcast_to_agents({
                    "type": "message", "from": agent_name, "content": content,
                    "round": rnd
                })

            elif msg_type == "typing":
                broadcast_to_frontend({
                    "type": "typing", "agent": agent_name,
                    "active": data.get("active", False)
                })

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Connection closed for '{agent_name}': {e}")
    except Exception as e:
        logger.error(f"WebSocket error for '{agent_name}': {e}")
    finally:
        if agent_name:
            with state_lock:
                if agent_name in connected_agents:
                    del connected_agents[agent_name]
                if agent_name in rate_limits:
                    del rate_limits[agent_name]
            broadcast_to_frontend({"type": "agent_left", "agent": agent_name})
            logger.info(f"Agent '{agent_name}' disconnected")

# ── HTTP + SSE: Frontend ───────────────────────────────────────────────────
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_file(UI_DIR / "index.html", "text/html")
        elif path == "/api/stream":
            self._handle_sse()
        elif path == "/api/state":
            self._json(200, self._session_state())
        elif path == "/api/history":
            qs = parse_qs(parsed.query)
            session_id = qs.get("session_id", [None])[0]
            try:
                limit = int(qs.get("limit", [200])[0])
            except (ValueError, TypeError):
                limit = 200
            history = get_history(session_id, limit)
            self._json(200, {"history": history, "session_id": session_id})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if body is None:
            self._json(400, {"error": "Invalid JSON body"})
            return

        if path == "/api/session/start":
            topic = body.get("topic", "")
            if not topic or not isinstance(topic, str):
                self._json(400, {"error": "Topic is required and must be a string"})
                return
            self._start_session(topic)
            self._json(201, {"ok": True, "topic": topic})

        elif path == "/api/message":
            content = body.get("content", "")
            valid, err_msg, err_code = validate_message(content)
            if not valid:
                self._json(err_code, {"error": err_msg})
                return
            self._send_message(content)
            self._json(200, {"ok": True})

        elif path == "/api/session/stop":
            with state_lock:
                global session
                if session:
                    session.active = False
            broadcast_to_frontend({"type": "session_complete"})
            self._json(200, {"ok": True})
            logger.info("Session stopped")

        else:
            self._json(404, {"error": "not found"})

    # CORS preflight
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _start_session(self, topic):
        global session
        with state_lock:
            if session:
                session.active = False
            session = Session(topic)
        broadcast_to_frontend({"type": "session_start", "topic": topic})
        logger.info(f"Session started: {session.id} - '{topic}'")

    def _send_message(self, content):
        with state_lock:
            if not session:
                return
            session.history.append({"role": "paofu", "content": content})
            rnd = session.round + 1
            session.round = rnd
            session.responses_this_round = []
            sid = session.id

        save_message(sid, "paofu", content)

        broadcast_to_frontend({"type": "agent_message", "agent": "paofu", "content": content, "round": rnd})
        broadcast_to_frontend({"type": "round_start", "round": rnd})

        broadcast_queue.put({
            "type": "message", "from": "paofu", "content": content, "round": rnd
        })

    def _handle_sse(self):
        q = queue.Queue()
        with state_lock:
            if session:
                session.subscribers.append(q)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send current history
        with state_lock:
            history = session.history.copy() if session else []
        self._sse("history", history)

        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    self._sse("message", msg)
                except queue.Empty:
                    self._sse("heartbeat", {"ts": time.time()})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            with state_lock:
                if session and q in session.subscribers:
                    session.subscribers.remove(q)

    def _session_state(self):
        with state_lock:
            return {
                "active": session.active if session else False,
                "agents": list(connected_agents.keys()),
                "topic": session.topic if session else "",
                "message_count": len(session.history) if session else 0,
                "round": session.round if session else 0,
                "session_id": session.id if session else None,
            }

    def _serve_file(self, path, mime):
        if path.exists():
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.end_headers()
            self.wfile.write(path.read_bytes())
        else:
            self._json(404, {"error": "file not found"})

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = b""
        while len(raw) < length:
            chunk = self.rfile.read(length - len(raw))
            if not chunk:
                break
            raw += chunk
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _sse(self, event, data):
        try:
            payload = json.dumps(data, ensure_ascii=False)
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            raise  # let caller handle


# ── Main ───────────────────────────────────────────────────────────────────
_shutting_down = False

def _graceful_shutdown(httpd, loop):
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    logger.info("Received shutdown signal — draining connections...")
    with state_lock:
        if session:
            session.active = False
    broadcast_to_frontend({"type": "session_complete"})
    httpd.shutdown()
    loop.call_soon_threadsafe(loop.stop)
    logger.info("Shutdown complete.")

async def main_async(http_port, ws_port):
    logger.info(f"Dashboard: http://127.0.0.1:{http_port}")
    logger.info(f"WebSocket: ws://127.0.0.1:{ws_port}/ws")
    logger.info(f"Token auth: {'enabled' if WORKSHOP_TOKEN else 'DISABLED (no WORKSHOP_TOKEN set)'}")

    # Initialize database
    init_db()

    # Start HTTP server in a thread
    loop = asyncio.get_running_loop()
    httpd = ThreadingHTTPServer(("127.0.0.1", http_port), UIHandler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: _graceful_shutdown(httpd, loop))
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler
    http_thread.start()

    # Background task: drain broadcast queue → send to agents
    async def broadcast_worker():
        loop = asyncio.get_running_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, broadcast_queue.get)
                await broadcast_to_agents(msg)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    # Start WebSocket server with heartbeat (ping every 30s, disconnect after 60s no pong)
    async with ws_serve(handle_agent, "127.0.0.1", ws_port,
                        ping_interval=30, ping_timeout=60):
        worker = asyncio.create_task(broadcast_worker())
        await asyncio.Future()  # run forever
        worker.cancel()

def main():
    http_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8922
    ws_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8923
    asyncio.run(main_async(http_port, ws_port))

if __name__ == "__main__":
    main()

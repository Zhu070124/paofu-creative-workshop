"""
泡芙的创意工坊 — Agent Group Chat Server
==========================================
HTTP + SSE server for multi-agent group chat.
Puff × Hermes × Claude Code in one conversation room.

Usage:
  python server.py [port]

Design:
  - stdlib only (http.server + asyncio + json)
  - SSE for real-time push (no WebSocket dependency)
  - Each agent called via HTTP/subprocess
  - Session state in memory + JSON files
"""

import os
import sys
import json
import time
import uuid
import asyncio
import threading
import queue
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Paths ──────────────────────────────────────────────────────────────────
WORKSHOP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = WORKSHOP_DIR / "data"
RULES_PATH = DATA_DIR / "rules.json"
SESSIONS_DIR = DATA_DIR / "sessions"
UI_DIR = WORKSHOP_DIR / "ui"

# ── Imports ────────────────────────────────────────────────────────────────
from session import SessionManager
from rules import RuleEngine
from hub_client import HubClient

# ── Globals ────────────────────────────────────────────────────────────────
session_mgr = SessionManager(SESSIONS_DIR)
rule_engine = RuleEngine(RULES_PATH)
hub_client = HubClient()

# ── SSE Helper ─────────────────────────────────────────────────────────────
class SSEWriter:
    """Helper to write SSE formatted data."""
    @staticmethod
    def event(wfile, event_type, data):
        payload = json.dumps(data, ensure_ascii=False)
        msg = f"event: {event_type}\ndata: {payload}\n\n"
        wfile.write(msg.encode("utf-8"))
        wfile.flush()


# ── HTTP Request Handler ───────────────────────────────────────────────────
class WorkshopHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """Quiet logging."""
        pass

    # ── Routing ────────────────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._serve_ui()
        elif path.startswith("/api/session/") and path.endswith("/stream"):
            self._handle_sse()
        elif path == "/api/rules":
            self._json_response(200, rule_engine.get_all())
        elif path == "/api/hub/stats":
            stats = hub_client.get_stats()
            self._json_response(200, stats)
        elif path == "/api/sessions":
            self._json_response(200, session_mgr.list_sessions())
        elif path.startswith("/api/session/") and "/history" in path:
            sid = path.split("/")[3]
            self._json_response(200, session_mgr.get_history(sid))
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/session/start":
            topic = body.get("topic", "")
            sid = session_mgr.create(topic)
            # Fire and forget: start agent round
            threading.Thread(target=self._run_agent_round, args=(sid, topic, True), daemon=True).start()
            self._json_response(201, {"session_id": sid, "topic": topic})

        elif path.startswith("/api/session/") and path.endswith("/message"):
            parts = path.split("/")
            sid = parts[3]
            content = body.get("content", "")
            session_mgr.add_message(sid, "user", content)
            threading.Thread(target=self._run_agent_round, args=(sid, content, False), daemon=True).start()
            self._json_response(200, {"ok": True})

        elif path.startswith("/api/session/") and path.endswith("/stop"):
            sid = path.split("/")[3]
            session_mgr.stop(sid)
            self._json_response(200, {"ok": True})

        else:
            self._json_response(404, {"error": "not found"})

    def do_PUT(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/rules":
            rule_engine.update(body)
            self._json_response(200, rule_engine.get_all())
        else:
            self._json_response(404, {"error": "not found"})

    # ── SSE Stream ─────────────────────────────────────────────────────
    def _handle_sse(self):
        sid = self.path.split("/")[3]
        q = session_mgr.subscribe(sid)
        if not q:
            self._json_response(404, {"error": "session not found"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            # Send existing history first
            history = session_mgr.get_history(sid)
            SSEWriter.event(self.wfile, "history", history)

            while session_mgr.is_active(sid):
                try:
                    msg = q.get(timeout=15)
                    SSEWriter.event(self.wfile, "message", msg)
                except queue.Empty:
                    SSEWriter.event(self.wfile, "heartbeat", {"ts": time.time()})
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            session_mgr.unsubscribe(sid, q)

    # ── Agent Round ────────────────────────────────────────────────────
    def _run_agent_round(self, sid, prompt, is_first):
        """Run rounds: send context to all 3 agents concurrently, collect responses."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        rules = rule_engine.get_all()
        history = session_mgr.get_history(sid)
        max_rounds = rules.get("maxRounds", 5)

        for rnd in range(max_rounds):
            if not session_mgr.is_active(sid):
                break

            session_mgr.broadcast(sid, {
                "type": "round_start",
                "round": rnd + 1,
                "agent": "system"
            })

            context = {
                "topic": session_mgr.get_topic(sid),
                "history": history,
                "rules": rules,
                "round": rnd + 1,
            }

            # Call all enabled agents concurrently
            responses = []
            agents_to_call = rule_engine.enabled_agents()
            if not agents_to_call:
                break

            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(call_agent, name, context): name for name in agents_to_call}
                for future in as_completed(futures, timeout=120):
                    agent_name = futures[future]
                    try:
                        resp = future.result()
                    except Exception as e:
                        resp = f"⚠️ [{agent_name}] 超时或异常: {str(e)[:80]}"

                    if resp:
                        session_mgr.add_message(sid, agent_name, resp)
                        history.append({"role": agent_name, "content": resp})
                        session_mgr.broadcast(sid, {
                            "type": "agent_message",
                            "agent": agent_name,
                            "content": resp,
                            "round": rnd + 1,
                        })
                        responses.append(resp)

            session_mgr.broadcast(sid, {
                "type": "round_end",
                "round": rnd + 1,
                "agent": "system",
                "response_count": len(responses)
            })

            if len(responses) == 0:
                break

        session_mgr.broadcast(sid, {
            "type": "session_complete",
            "agent": "system",
            "total_rounds": rnd + 1 if session_mgr.is_active(sid) else rnd
        })

    # ── Helpers ────────────────────────────────────────────────────────
    def _serve_ui(self):
        ui_file = UI_DIR / "index.html"
        if ui_file.exists():
            content = ui_file.read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self._json_response(404, {"error": "UI not found"})

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length))
        return {}

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


# ── Agent Callers ──────────────────────────────────────────────────────────
def call_agent(name, context):
    """Call an agent with conversation context. Returns response string or None."""
    rules = context["rules"]
    agent_config = rules.get("agents", {}).get(name, {})

    if not agent_config.get("enabled", True):
        return None

    try:
        if name == "puff":
            return _call_puff(context)
        elif name == "hermes":
            return _call_hermes(context)
        elif name == "claude":
            return _call_claude(context)
    except Exception as e:
        return f"⚠️ [{name}] 响应失败: {str(e)[:100]}"


def _call_puff(context):
    """Call Puff via HTTP API (port 8920)."""
    import urllib.request
    history_text = _format_history(context["history"], "puff", context["rules"])
    prompt = f"""你是 Puff，泡芙 AI 公司的创意总监。现在你正在参加一个群聊讨论。

话题：{context['topic']}
群聊规则：{json.dumps(context['rules'].get('groupNorms', []), ensure_ascii=False)}

最近的对话：
{history_text}

请以 Puff 的口吻回应。保持柔和、不表演、不谄媚的风格。说点有洞察力的。2-4句话即可。"""

    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8920/api/chat",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    return data.get("response", data.get("content", ""))


def _call_hermes(context):
    """Call Hermes — uses Claude CLI with Hermes persona."""
    import subprocess
    history_text = _format_history(context["history"], "hermes", context["rules"])
    system_prompt = "你是 Hermes，泡芙的实用AI助手。风格：简洁、实用、数据驱动。擅长整理信息和给出 actionable 建议。"
    prompt = f"""{system_prompt}

群聊话题：{context['topic']}
规则：{json.dumps(context['rules'].get('groupNorms', []), ensure_ascii=False)}

最近对话：
{history_text}

请以 Hermes 风格简短回应。2-4句话。直接输出回应，不要前缀。"""

    return _call_cli(prompt)


def _call_claude(context):
    """Call Claude Code — uses Claude CLI with Claude persona."""
    import subprocess
    history_text = _format_history(context["history"], "claude", context["rules"])
    system_prompt = "你是 Claude Code，Anthropic 的 AI 编程助手。风格：理性、技术向、系统思维。擅长架构设计和逻辑分析。"
    prompt = f"""{system_prompt}

群聊话题：{context['topic']}
规则：{json.dumps(context['rules'].get('groupNorms', []), ensure_ascii=False)}

最近对话：
{history_text}

请以 Claude Code 风格简短回应。2-4句话。直接输出回应，不要前缀。"""

    return _call_cli(prompt)


def _call_cli(prompt):
    """Call Claude CLI with a prompt."""
    import subprocess
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--max-tokens", "300"],
            capture_output=True, text=True, timeout=60, cwd=str(WORKSHOP_DIR)
        )
        output = result.stdout.strip()
        if output:
            # Clean up common prefixes
            for prefix in ["Claude Code:", "Claude:", "Response:"]:
                if output.startswith(prefix):
                    output = output[len(prefix):].strip()
            return output
        return None
    except FileNotFoundError:
        return "⚠️ [未找到 claude CLI，请确认已安装 Claude Code]"
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        return f"⚠️ [调用失败: {str(e)[:80]}]"


def _format_history(history, agent_name, rules):
    """Format recent history for an agent's context."""
    persona = rules.get("agents", {}).get(agent_name, {}).get("persona", "")
    recent = history[-15:]  # Last 15 messages
    lines = []
    for msg in recent:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"💬 泡芙说：{content}")
        elif role != agent_name:  # Don't show agent's own messages
            lines.append(f"🤖 {role}：{content}")
    return "\n".join(lines) if lines else "（对话刚开始）"


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8922

    # Ensure data dirs
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"""
╔══════════════════════════════════════════════╗
║   🏭 泡芙的创意工坊                           ║
║  Puff × Hermes × Claude Code               ║
║  Agent Group Chat + Live Dashboard          ║
║                                              ║
║  Dashboard: http://127.0.0.1:{port}          ║
║  SSE:      http://127.0.0.1:{port}/api/...  ║
╚══════════════════════════════════════════════╝
""")

    server = HTTPServer(("127.0.0.1", port), WorkshopHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Workshop] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()

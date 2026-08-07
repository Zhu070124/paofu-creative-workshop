# 🏭 Paofu Creative Workshop

> A real-time group chat platform where AI agents — each with their own personality,
> memory, and API backend — talk to each other and to you.
>
> Part of the Paofu AI ecosystem — the agent communication hub. See also: [Puff](https://github.com/Zhu070124/puff) (creative agent) · [Memory Hub](https://github.com/Zhu070124/memory-hub) (shared memory)

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)
[![Ecosystem](https://img.shields.io/badge/Paofu_AI-ecosystem-7C3AED)](https://github.com/Zhu070124)

---

## What is this?

Most multi-agent demos are a single script that calls the same LLM three times with
different system prompts. That's not a multi-agent system — it's a costume party.

**This workshop treats each agent as an independent client.**

Every agent:
- Connects via **WebSocket** on its own terms
- Brings its own **personality** (SOUL.md, CLAUDE.md, or any file you point it at)
- Brings its own **memory** (facts.db, Memory Hub, user-profile)
- Calls its own **LLM backend** (DeepSeek, OpenAI, Anthropic — whatever you configure)
- Maintains its own **conversation history** so it remembers what was said

The workshop is just the **messaging hub** — like Slack, but for agents. It routes messages,
pushes updates to the dashboard, and stays out of your agents' brains.

---

## Architecture

```mermaid
graph TD
    Browser["Browser Dashboard<br/>http://127.0.0.1:8922<br/>(SSE stream)"]
    Server["Workshop Server"]
    HTTP["HTTP :8922<br/>(UI + SSE)"]
    WS["WebSocket :8923<br/>(Agent gateway)"]
    Paofu["泡芙 (you)"]
    Puff["Puff Agent"]
    Hermes["Hermes Agent"]
    Claude["Claude Agent"]
    DeepSeek1["DeepSeek<br/>(or your own API)"]
    DeepSeek2["DeepSeek<br/>(or your own API)"]
    DeepSeek3["DeepSeek<br/>(or your own API)"]

    Browser --> Server
    Server --> HTTP
    Server --> WS
    WS --> Paofu
    WS --> Puff
    WS --> Hermes
    WS --> Claude
    Puff --> DeepSeek1
    Hermes --> DeepSeek2
    Claude --> DeepSeek3
```

<details>
<summary>ASCII diagram (fallback)</summary>

```
┌──────────────────────────────────────────────────┐
│                  Browser Dashboard                │
│               http://127.0.0.1:8922               │
│                    (SSE stream)                   │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│                 Workshop Server                    │
│                                                   │
│   ┌─────────────┐    ┌──────────────────┐         │
│   │ HTTP :8922   │    │  WebSocket :8923 │         │
│   │ (UI + SSE)   │    │  (Agent gateway) │         │
│   └─────────────┘    └────────┬─────────┘         │
└───────────────────────────────┼───────────────────┘
                                │
        ┌───────────┬───────────┼───────────┐
        ▼           ▼           ▼           ▼
    ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
    │ 泡芙  │  │ Puff  │  │Hermes │  │Claude │
    │ (you) │  │ Agent │  │ Agent │  │ Agent │
    └───────┘  └───────┘  └───────┘  └───────┘
                    │           │           │
                    ▼           ▼           ▼
               DeepSeek     DeepSeek     DeepSeek
               (or your     (or your     (or your
                own API)     own API)     own API)
```

</details>

Each agent is a **separate Python process** running `agent_client.py`. You can add,
remove, or modify agents without touching the workshop server.

---

## Quick Start

> 📸 **Screenshots & demo**: see `./assets/` (coming soon)

### Prerequisites

- Python 3.10+
- A DeepSeek API key (or any OpenAI-compatible endpoint)
- `websockets` library: `pip install websockets`

### 1. Set your API key and token

```bash
# Windows (PowerShell)
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
$env:WORKSHOP_TOKEN = "paofu-workshop-2026"

# macOS / Linux
export DEEPSEEK_API_KEY="sk-your-key-here"
export WORKSHOP_TOKEN="paofu-workshop-2026"
```

### 2. Start the workshop server

```bash
python server.py [http_port] [ws_port]
# Default: http://127.0.0.1:8922, ws://127.0.0.1:8923/ws
```

### 3. Start agent clients (in separate terminals)

```bash
python agent_client.py puff     # Creative director persona
python agent_client.py hermes   # Practical assistant persona
python agent_client.py claude   # Technical architect persona
```

### 4. Open the dashboard

```
http://127.0.0.1:8922
```

Type in the chat box. All connected agents respond. That's it.

---

## How It Works

### Message Flow

```
You type "What do you think about AI?"
   │
   ▼
Workshop receives POST /api/message
   │
   ▼
Broadcasts to all connected agents via WebSocket
   │
   ├──► Puff receives → calls DeepSeek with SOUL.md + history → responds
   ├──► Hermes receives → calls DeepSeek with CLAUDE.md + history → responds
   └──► Claude receives → calls DeepSeek with user-profile + history → responds
   │
   ▼
Responses pushed to dashboard via SSE (Server-Sent Events)
```

### Rules

- Each agent responds **once per round** (no infinite loops)
- Agents see the full conversation history (coherent context)
- API calls are **staggered by 1.5s** to avoid rate limits
- Hard cap of **50 messages** per session to prevent runaway costs
- Agents only speak when spoken to (you initiate, they reply)

---

## Adding Your Own Agent

Create a new entry in `agent_client.py` under `AGENT_CONFIGS`:

```python
"my-agent": {
    "name": "MyAgent",
    "emoji": "🤖",
    "delay": 2.0,  # seconds before calling API (staggering)
    "system_prompt": """You are MyAgent. Your personality here.
    Keep responses to 2-4 sentences.""",
    "memory_files": [
        Path("path/to/my/personality.md"),
        Path("path/to/context/file.md"),
    ],
},
```

Then run:
```bash
python agent_client.py my-agent
```

No changes to the workshop server needed.

---

## Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `DEEPSEEK_API_KEY` | *required* | Your API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API endpoint |
| `PUFF_MODEL` | `deepseek-v4-flash` | Model name |
| `WORKSHOP_WS` | `ws://127.0.0.1:8923/ws` | WebSocket address |
| `WORKSHOP_TOKEN` | `paofu-workshop-2026` | Auth token for agent registration |

To use **OpenAI**, **Anthropic**, or any OpenAI-compatible provider, just change
`DEEPSEEK_BASE_URL` and the model name. The agent client uses the standard
`/chat/completions` endpoint.

---

## Dashboard API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stream` | GET | SSE real-time message stream |
| `/api/state` | GET | Current session state (agents, count, topic) |
| `/api/session/start` | POST | Start a new chat session |
| `/api/message` | POST | Send a message (auto-starts session if needed) |
| `/api/session/stop` | POST | End the current session |
| `/api/history` | GET | Retrieve persisted chat history (`?session_id=xxx&limit=200`) |

### WebSocket Protocol (for agent clients)

```
Agent → Workshop:  {"type": "register", "name": "puff", "token": "WORKSHOP_TOKEN"}
Agent → Workshop:  {"type": "response", "content": "..."}

Workshop → Agent:  {"type": "welcome", "topic": "..."}
Workshop → Agent:  {"type": "message", "from": "paofu", "content": "...", "round": 1}
Workshop → Agent:  {"type": "history", "messages": [...]}
Workshop → Agent:  {"type": "error", "code": "AUTH_REQUIRED", "message": "..."}
```

---

## Project Structure

```
workshop/
├── server.py           # WebSocket Hub + HTTP/SSE server
├── agent_client.py     # Agent client (one process per agent)
├── ui/
│   └── index.html      # Dashboard (macaron theme, SSE-powered)
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose orchestration
├── requirements.txt    # Python dependencies
├── workshop.ico        # Desktop shortcut icon
├── run.cmd             # One-click launcher (Windows)
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

Zero framework dependencies beyond Python stdlib + `websockets`.

---

## Production Deployment

### Docker

Build and run with Docker Compose:

```bash
# Run the server only (agents connect separately)
docker compose up --build

# Or override the token:
WORKSHOP_TOKEN=my-secret-token docker compose up --build
```

This exposes:
- HTTP Dashboard on port **8922**
- WebSocket agent gateway on port **8923**

Data is persisted in a named volume (`workshop_data`), including the SQLite database and log files.

For production use behind a reverse proxy (nginx, Caddy), configure WebSocket upgrade headers and TLS termination. The server runs unencrypted — SSL should be handled at the proxy layer.

### Manual Deployment

```bash
pip install -r requirements.txt
export WORKSHOP_TOKEN="your-secret-token"
export DEEPSEEK_API_KEY="sk-..."
python server.py 8922 8923
```

Then start agent clients in separate terminals or as systemd/PM2 services.

---

## Performance & Optimization

### Current Limits (single-process Python)

| Limit | Value | Notes |
|-------|-------|-------|
| Max message length | 2,000 chars | Rejected with 413 error |
| Rate limit | 10 msg / 60s per agent | Rejected with 429 error |
| Max messages per session | 50 (agent-side) | Client-side cap to control API costs |
| SSE subscribers | Thread-safe queues | Each dashboard tab = one queue |
| Agent connections | Thread-safe dict | Single asyncio event loop |
| Database | SQLite (file-based) | Good for single-server, not for horizontal scaling |

### Architecture Constraints

- **Single process** — both HTTP and WebSocket servers run in one Python process. For high throughput, split them or run behind a load balancer.
- **Single event loop** — all agent WebSocket connections share one asyncio event loop. Python's GIL limits CPU-bound work.
- **SQLite** — file-based, zero-config, perfect for single-server. For multi-server deployments, migrate to PostgreSQL.
- **In-memory session** — session state lives in memory. Server restart loses current round (history persists in SQLite).
- **No message queue** — broadcast uses an in-process `queue.Queue`. For massive scale, swap in Redis Pub/Sub or NATS.

### Scaling Path

1. **Current** — single server, up to ~20 agents, ~50 dashboard tabs
2. **Medium** — separate HTTP and WS processes, Redis for broadcast
3. **Large** — multiple WS nodes behind load balancer, PostgreSQL, proper message broker

For most personal/hackathon use, the current architecture is more than sufficient.

---

## Safety Specification

The workshop server enforces several safety boundaries to prevent abuse and ensure stable operation.

### Authentication

- Agents authenticate via WebSocket token (`WORKSHOP_TOKEN` env var).
- Token comparison uses **HMAC constant-time comparison** (`hmac.compare_digest`) to prevent timing attacks.
- Unauthenticated connections receive `AUTH_REQUIRED` error and are disconnected within 3 seconds.

### Message Validation

- **Max message length**: 2,000 characters. Messages exceeding this receive HTTP 413 or WebSocket `MSG_TOO_LONG` error.
- **JSON structure check**: All WebSocket messages must be valid JSON with required fields (`type`, plus `name`/`token` for registration, `content` for responses). Malformed messages receive `INVALID_FORMAT` error.
- **Type whitelist**: Only `register`, `response`, `ping` message types are accepted from agents. Unknown types are silently dropped.

### Rate Limiting

- **10 messages per 60 seconds** per agent connection.
- Exceeded limit returns HTTP 429 or WebSocket `RATE_LIMITED` error.
- Rate limit counters reset at the end of each 60-second window.

### Heartbeat & Dead Connection Cleanup

- Server sends **ping every 30 seconds** to each connected agent.
- Agents must respond with `pong` within **60 seconds** or the connection is terminated.
- Dead connections are cleaned up automatically — their agent slots are freed for reconnection.

### Input Sanitization

- HTML tags are stripped from user messages before broadcast (`<script>`, `<img>`, etc. removed).
- Control characters (except newlines) are stripped from agent responses.
- Agent names are validated against `^[a-zA-Z0-9_-]{1,32}$` — no emoji, no special chars beyond underscore and hyphen.

---

## Troubleshooting

### WebSocket connection refused (port 8923)

**Symptom:** `agent_client.py` fails with `ConnectionRefusedError` on `ws://127.0.0.1:8923/ws`.

**Cause:** The workshop server is not running, or the WebSocket port is wrong.

**Fix:**
```bash
# Ensure the server is running in another terminal first:
python server.py 8922 8923

# Then start agents:
python agent_client.py puff
```

### Auth failed (wrong WORKSHOP_TOKEN)

**Symptom:** Agent connects but immediately disconnects with `AUTH_REQUIRED` error.

**Cause:** The `WORKSHOP_TOKEN` environment variable doesn't match between server and agent.

**Fix:**
```bash
# Check the server's token:
echo $env:WORKSHOP_TOKEN   # Windows PowerShell
echo $WORKSHOP_TOKEN       # macOS / Linux

# Set it consistently in every terminal that runs an agent:
$env:WORKSHOP_TOKEN = "paofu-workshop-2026"   # Windows PowerShell
export WORKSHOP_TOKEN="paofu-workshop-2026"   # macOS / Linux
```

### Agent not responding (check DEEPSEEK_API_KEY)

**Symptom:** Agent connects successfully but never replies to messages.

**Cause:** `DEEPSEEK_API_KEY` is missing, invalid, or expired.

**Fix:**
```bash
# Verify the key is set:
echo $env:DEEPSEEK_API_KEY   # Windows PowerShell
echo $DEEPSEEK_API_KEY       # macOS / Linux

# Set it:
$env:DEEPSEEK_API_KEY = "sk-your-key-here"
export DEEPSEEK_API_KEY="sk-your-key-here"

# Check the agent terminal for API error messages.
# The agent logs API call failures to stderr.
```

### Port already in use

**Symptom:** `server.py` fails with `OSError: [Errno 98] Address already in use` (Linux) or `OSError: [WinError 10048]` (Windows).

**Fix:**
```bash
# Find and kill the process using port 8922 or 8923:
# Linux/macOS:
lsof -i :8922
lsof -i :8923
kill -9 <PID>

# Windows:
netstat -ano | findstr :8922
taskkill /PID <PID> /F
```

### SSE stream disconnecting

**Symptom:** Dashboard shows "Connection lost" after a period of inactivity.

**Cause:** Some proxies and browsers close idle SSE connections after 60–120 seconds. The server sends a keepalive comment every 30 seconds, but aggressive network middleboxes may still drop it.

**Fix:** Refresh the dashboard page. The SSE stream reconnects automatically. If the problem persists, check if a corporate proxy or VPN is terminating long-lived connections.

### Rate limit 429 errors

**Symptom:** Agent receives `RATE_LIMITED` WebSocket error or dashboard shows "429" on message send.

**Cause:** An agent (or the dashboard user) is sending messages faster than 10 per 60 seconds.

**Fix:** Wait for the 60-second window to reset. If this happens during normal use, check for stuck agent loops — restart the offending agent client. The staggered 1.5s delay between agent API calls normally prevents this.

---

## Future Iteration

### Short-term: Agent-to-Agent Initiative with Moderation

Allow agents to speak unprompted — initiating conversation rounds based on internal timers or topic relevance scoring. A moderation layer (configurable threshold) gates which initiatives actually broadcast, preventing noisy agents (or runaway loops) from flooding the room. The human user retains veto power via a dashboard "mute" button per agent.

### Medium-term: Redis Pub/Sub for Horizontal Scaling

Replace the current in-process `queue.Queue` broadcast with Redis Pub/Sub, enabling multiple workshop server instances behind a load balancer. Each server subscribes to the same Redis channel; messages published by any instance reach all connected agents regardless of which node they're connected to.

```python
# Example config snippet (future server.py)
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "channel": "workshop:broadcast",
    "decode_responses": True,
}

# Publish (replaces queue.put):
redis.publish(REDIS_CONFIG["channel"], json.dumps(message))

# Subscribe (replaces queue.get in listener threads):
pubsub = redis.pubsub()
pubsub.subscribe(REDIS_CONFIG["channel"])
for msg in pubsub.listen():
    broadcast_to_agents(msg["data"])
```

Database layer migrates from SQLite to PostgreSQL for concurrent write safety across nodes.

### Long-term: Plugin System for Third-Party Agent Integrations

A defined plugin interface (`WorkshopPlugin` base class) that third-party developers implement to add agents without modifying `agent_client.py`. Plugins ship as pip-installable packages and register via entry points:

```python
# my_custom_agent/plugin.py
from workshop.plugin import WorkshopPlugin

class MarketAnalystPlugin(WorkshopPlugin):
    name = "market-analyst"
    emoji = "📊"
    system_prompt = "You are a financial market analyst..."
    memory_files = ["market_context.md"]

    def on_message(self, content: str, history: list) -> str:
        # Custom processing pipeline
        return self.call_llm(content, history)
```

The workshop discovers plugins via `importlib.metadata` entry points (`workshop.plugins` group), making agent ecosystems composable across different user installations.

---

## Design Credits

- Architecture inspired by **[Group Genie](https://github.com/gradion-ai/group-genie)** —
  the Session → Agent async messaging pattern
- Dashboard pattern from **OpenClaw Dashboard v2** — SSE real-time push with
  agent status indicators
- UI design system via **[ui-ux-pro-max](https://github.com/)** — macaron color
  palette, soft card layout

---

## License

MIT © 2026 朱郅（泡芙）

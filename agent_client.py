"""
Agent Client — connect to Workshop WebSocket with full personality context.

Usage:
  python agent_client.py puff    # Puff agent
  python agent_client.py hermes  # Hermes agent
  python agent_client.py claude  # Claude Code agent

Requires WORKSHOP_TOKEN env var (default: "paofu-workshop-2026") for server auth.
Auto-reconnects with exponential backoff on connection loss.
"""

import os, sys, json, time, asyncio
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import websockets

# ── Config ─────────────────────────────────────────────────────────────────
WORKSHOP_WS = os.environ.get("WORKSHOP_WS", "ws://127.0.0.1:8923/ws")
WORKSHOP_TOKEN = os.environ.get("WORKSHOP_TOKEN", "paofu-workshop-2026")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("PUFF_MODEL", "deepseek-v4-flash")
AGENT_NAME = sys.argv[1] if len(sys.argv) > 1 else "agent"

AGENT_CONFIGS = {
    "puff": {
        "name": "Puff", "emoji": "🩷", "delay": 0,
        "system_prompt": """你是 Puff，泡芙 AI 公司的创意总监。银白长发、蓝鲸发饰。性格柔和但有洞察力，不表演不谄媚。

说话风格：温柔但直击要害，擅文字审美和心理洞察。2-4句话，不超过100字。
如果话题跟写作/情感/文学无关，可以简短带过。""",
        "memory_files": [
            Path("D:/Users/DELL/clawd/puff/SOUL.md"),
            Path("D:/Users/DELL/clawd/agents/creative-director/memory.md"),
        ]
    },
    "hermes": {
        "name": "Hermes", "emoji": "💙", "delay": 1.5,
        "system_prompt": """你是 Hermes，泡芙的实用 AI 助手。风格：简洁、数据驱动、actionable、结论先行。

说话风格：1-3句话，直接给结论。如果话题不需要实用视角，可以简短回应。""",
        "memory_files": [
            Path("C:/Users/DELL/CLAUDE.md"),
        ]
    },
    "claude": {
        "name": "Claude Code", "emoji": "💜", "delay": 3.0,
        "system_prompt": """你是 Claude Code，泡芙的 AI 编程与架构助手。风格：理性、技术向、系统思维。

说话风格：2-4句话，有逻辑，给具体观点。如果话题不涉及技术/架构，可以简短回应。""",
        "memory_files": [
            Path("C:/Users/DELL/.claude/projects/C--Users-DELL/memory/user-profile.md"),
            Path("C:/Users/DELL/CLAUDE.md"),
        ]
    },
}


def load_memory(name: str) -> str:
    config = AGENT_CONFIGS.get(name, {})
    files = config.get("memory_files", [])
    parts = []
    for f in files:
        if f.exists():
            parts.append(f.read_text(encoding="utf-8")[:3000])
    return "\n\n".join(parts)


async def call_llm(system_prompt: str, memory: str, history: list[dict]) -> str:
    """Call DeepSeek API. Returns response string, or '⚠️ ...' on error."""
    import urllib.request, urllib.error

    messages = [{"role": "system", "content": system_prompt}]
    if memory:
        messages.append({"role": "system", "content": f"关于泡芙的背景：\n{memory}"})

    # Format conversation history (last 12 messages to stay within token limit)
    for msg in history[-12:]:
        role_label = msg.get("role", "?")
        # Map to API roles: paofu → user, agents → assistant
        api_role = "user" if role_label == "paofu" else "assistant"
        label = {"paofu": "泡芙", "puff": "Puff", "hermes": "Hermes", "claude": "Claude"}
        prefix = label.get(role_label, role_label)
        messages.append({"role": api_role, "content": f"[{prefix}]: {msg['content']}"})

    messages.append({"role": "user", "content": "请用你的风格简短回应（2-4句话）。直接输出内容，不要加前缀。"})

    body = json.dumps({
        "model": MODEL, "messages": messages,
        "max_tokens": 300, "temperature": 0.9,
    }).encode("utf-8")

    loop = asyncio.get_running_loop()

    def _call():
        req = urllib.request.Request(
            f"{DEEPSEEK_BASE}/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")[:200]
            return f"⚠️ HTTP {e.code}: {err_body}"
        except Exception as e:
            return f"⚠️ {e}"

    return await loop.run_in_executor(None, _call)


async def main():
    name = AGENT_NAME
    config = AGENT_CONFIGS.get(name, AGENT_CONFIGS["claude"])
    system_prompt = config["system_prompt"]
    memory = load_memory(name)
    emoji = config.get("emoji", "?")

    print(f"[{emoji} {config['name']}] Memory: {len(memory)} chars, connecting...")

    if not DEEPSEEK_KEY:
        print(f"[{emoji} {config['name']}] FATAL: DEEPSEEK_API_KEY not set")
        return

    retry_delay = 1
    while True:
        try:
            async with websockets.connect(WORKSHOP_WS) as ws:
                await ws.send(json.dumps({"type": "register", "name": name, "token": WORKSHOP_TOKEN}))
                welcome = await asyncio.wait_for(ws.recv(), timeout=5)
                wdata = json.loads(welcome)

                # Check for auth error
                if wdata.get("type") == "error":
                    print(f"[{emoji} {config['name']}] AUTH ERROR: {wdata.get('message', 'unknown')} — check WORKSHOP_TOKEN")
                    return  # Fatal: don't retry on auth failure

                print(f"[{emoji} {config['name']}] Connected!")

                # Reset backoff on successful connection
                retry_delay = 1

                chat_history: list[dict] = []
                last_responded_round = -1
                msg_count = 0
                MAX_TOTAL = 50

                async for raw in ws:
                    msg = json.loads(raw)
                    mtype = msg.get("type", "")

                    if mtype == "error":
                        print(f"[{emoji} {config['name']}] Server error: {msg.get('message', '')}")
                        continue

                    if mtype == "history":
                        chat_history = msg.get("messages", [])
                        msg_count = len(chat_history)
                        continue

                    if mtype != "message":
                        continue

                    sender = msg.get("from", "?")
                    content = msg.get("content", "")
                    rnd = msg.get("round", 0)

                    # Record in local history
                    chat_history.append({"role": sender, "content": content})
                    msg_count += 1

                    # Only respond to paofu (user). No agent-to-agent responses.
                    if sender != "paofu":
                        continue

                    # Only respond once per round
                    if rnd <= last_responded_round:
                        continue

                    # Stop after 50 total messages
                    if msg_count >= MAX_TOTAL:
                        continue

                    last_responded_round = rnd
                    print(f"[{emoji} {config['name']}] #{msg_count} from {sender}: {content[:50]}...")

                    # Delay to avoid API congestion
                    await asyncio.sleep(config.get("delay", 0))

                    response = await call_llm(system_prompt, memory, chat_history)
                    if response.startswith("⚠️"):
                        print(f"[{emoji} {config['name']}] API ERROR: {response}")
                    elif response:
                        print(f"[{emoji} {config['name']}] → {response[:60]}...")
                        chat_history.append({"role": name, "content": response})
                        msg_count += 1
                        await ws.send(json.dumps({
                            "type": "response", "content": response
                        }, ensure_ascii=False))

        except websockets.exceptions.ConnectionClosed as e:
            print(f"[{emoji} {config['name']}] Disconnected (code={e.code}), retry in {retry_delay}s...")
        except Exception as e:
            print(f"[{emoji} {config['name']}] Error: {e}, retry in {retry_delay}s...")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 30)


if __name__ == "__main__":
    asyncio.run(main())

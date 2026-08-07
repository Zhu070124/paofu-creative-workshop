# Contributing to Paofu Creative Workshop

Thanks for your interest in contributing. This document outlines the process and guidelines.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Adding a New Agent](#adding-a-new-agent)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

---

## Code of Conduct

Be respectful. Be constructive. Assume good intent.

This project is a creative space — ideas are welcome, criticism should be actionable, and everyone is here to build something interesting.

---

## Getting Started

### Prerequisites

- Python 3.10+
- A DeepSeek API key (or any OpenAI-compatible endpoint)
- `websockets` library

### Setup

```bash
# Clone the repo
git clone https://github.com/Zhu070124/workshop.git
cd workshop

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DEEPSEEK_API_KEY="sk-your-key-here"
export WORKSHOP_TOKEN="paofu-workshop-2026"

# Start the server
python server.py

# In another terminal, start an agent
python agent_client.py puff
```

---

## Development Workflow

1. **Find or create an issue** for what you want to work on.
2. **Branch from `main`**: `git checkout -b feature/my-change` or `git checkout -b fix/my-bug`.
3. **Make your changes**. Keep commits small and focused.
4. **Test locally**: start the server and at least one agent, send messages through the dashboard, verify behavior.
5. **Push and open a PR** against `main`.

### Running Tests

```bash
# Manual integration test (start these in separate terminals):
# Terminal 1: python server.py
# Terminal 2: python agent_client.py puff
# Terminal 3: python agent_client.py hermes
# Then open http://127.0.0.1:8922 and send messages.
# Verify: both agents respond, SSE stream is live, no errors in any terminal.
```

---

## Coding Standards

- **Python**: Follow PEP 8. 4-space indentation. Type hints where practical.
- **No frameworks**: This project intentionally avoids Django, Flask, FastAPI. Core dependencies are Python stdlib + `websockets`.
- **Keep it simple**: Single-file modules (`server.py`, `agent_client.py`). If a file exceeds ~800 lines, consider extracting a module.
- **Comments in English**: Code comments and docstrings should be in English.
- **Error handling**: All network calls should have try/except. Agents should reconnect on connection loss.
- **Logging**: Use `print()` with timestamps for server logs. No logging framework needed.

### Commit Messages

```
type: short description (imperative mood)

Optional body explaining why, not what.
```

Types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`.

Example: `feat: add agent heartbeat with 30s ping interval`

---

## Adding a New Agent

Agents are defined in `AGENT_CONFIGS` dict inside `agent_client.py`. To add one:

```python
"my-agent": {
    "name": "MyAgent",
    "emoji": "🤖",
    "delay": 2.0,
    "system_prompt": """You are MyAgent. Your personality here.
    Keep responses to 2-4 sentences.""",
    "memory_files": [
        Path("path/to/my/personality.md"),
    ],
},
```

### Guidelines for Agent Personas

- Each agent should have a **distinct voice** — don't add agents that are just renamed copies.
- Keep system prompts **concise** (under 500 words). Long prompts increase token costs without proportional value.
- The `delay` field controls API call staggering. Don't set it below 1.0s — this prevents rate limiting on shared API keys.
- Memory files should be small Markdown files under 2KB. Large files bloat context windows.

---

## Pull Request Process

1. Ensure your branch is up to date with `main` before opening a PR.
2. Describe **what** changed and **why** in the PR description.
3. If the change affects the WebSocket protocol or dashboard API, update the README sections accordingly.
4. The maintainer reviews within 48 hours. Address feedback promptly.
5. Once approved, the maintainer squashes and merges.

---

## Reporting Bugs

Include:

- **What you were doing**: steps to reproduce.
- **What you expected**: the intended behavior.
- **What happened**: error messages, terminal output, screenshots.
- **Environment**: OS, Python version (`python --version`), browser if UI-related.

Template:

```
### Steps to reproduce
1. Start server with `python server.py`
2. Start agent with `python agent_client.py puff`
3. Send message "hello" from dashboard
4. ...

### Expected
Agent responds within reasonable time.

### Actual
Agent connects but never replies. Terminal shows:
    ERROR: API call failed: 401 Unauthorized

### Environment
- OS: Windows 11
- Python: 3.12.4
- Browser: Chrome 127
```

---

## Feature Requests

Open an issue with the `enhancement` label. Describe:

- The **problem** the feature solves.
- A **sketch** of how it might work (don't over-specify — a paragraph is enough).
- Why it fits the workshop's scope (agent communication hub, not a general platform).

Features that align with the [Future Iteration](README.md#future-iteration) roadmap are especially welcome.

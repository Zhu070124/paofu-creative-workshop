# 🏭 泡芙的创意工坊

> Multi-Agent Group Chat + Live Dashboard
> Puff × Hermes × Claude Code 在同一个房间里对话

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![stdlib](https://img.shields.io/badge/deps-0%20(zero)-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

---

## 🎯 这是什么

一个让三个 AI Agent（Puff、Hermes、Claude Code）在同一话题下自由对话的实时群聊系统。

你输入一个话题 → 三个 Agent 各自用自己的风格回应 → 对话推送到 Dashboard 实时展示。群聊规则可随时编辑，Agent 可在对话过程中读写 Memory Hub。

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                  泡芙的创意工坊 (:8922)                    │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │  Puff    │   │  Hermes  │   │  Claude   │            │
│  │  HTTP API│   │   CLI    │   │   CLI     │            │
│  └────┬─────┘   └────┬─────┘   └────┬──────┘            │
│       │              │              │                    │
│       └──────────────┼──────────────┘                    │
│                      │                                   │
│              ┌───────▼────────┐                          │
│              │ Session Manager│                          │
│              │  + Rule Engine │                          │
│              └───────┬────────┘                          │
│                      │                                   │
│         ┌────────────┼────────────┐                      │
│         │            │            │                      │
│    ┌────▼───┐  ┌─────▼────┐ ┌───▼──────┐                │
│    │  SSE   │  │  Rules   │ │  Memory  │                │
│    │ Stream │  │  Editor  │ │  Hub R/W │                │
│    └────┬───┘  └──────────┘ └──────────┘                │
│         │                                                │
└─────────┼────────────────────────────────────────────────┘
          │
    ┌─────▼──────┐
    │  Dashboard │
    │  Dark UI   │
    └────────────┘
```

## 🚀 快速开始

```bash
# 1. 确保 Memory Hub 和 Puff 在运行
python D:/Users/DELL/clawd/memory-hub/hub.py serve &
python D:/Users/DELL/clawd/puff/puff.py serve &

# 2. 启动工坊
python server.py

# 3. 打开浏览器
# http://127.0.0.1:8922
```

或双击 `run.cmd`

## 📡 API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/session/start` | POST | 创建群聊会话 |
| `/api/session/{id}/message` | POST | 发送用户消息 |
| `/api/session/{id}/stream` | GET | SSE 实时流 |
| `/api/session/{id}/stop` | POST | 结束会话 |
| `/api/rules` | GET/PUT | 查看/编辑规则 |
| `/api/hub/stats` | GET | Memory Hub 统计 |

## ⚙ 群聊规则

规则可通过 Dashboard 实时编辑，也可直接修改 `data/rules.json`：

- **maxRounds**: 最大对话轮次
- **groupNorms**: 群聊行为规范
- **agents**: 每个 Agent 的角色、人格、触发词、开关
- **moderation**: 审批模式、token 限制

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `server.py` | HTTP + SSE 服务主程序 |
| `session.py` | 会话管理器 |
| `rules.py` | 规则引擎 |
| `hub_client.py` | Memory Hub 客户端 |
| `ui/index.html` | Dashboard 前端（dark theme） |
| `data/` | 规则和会话持久化 |

## 🎨 设计参考

- **Group Genie** (gradion-ai/group-genie): Session → Reasoner → Agent 架构模式
- **OpenClaw Dashboard v2**: SSE 实时推送 + dark theme 仪表盘
- **Memory Hub**: 跨 Agent 记忆共享

## 👤 分工说明

本项目由**朱郅（泡芙）**独立完成。

架构设计和代码实现由 AI 编码助手辅助。

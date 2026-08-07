"""
Rule Engine — editable chat rules for agent group conversations.
"""

import json
from pathlib import Path


DEFAULT_RULES = {
    "maxRounds": 3,
    "responseStyle": "free_form",
    "maxResponseLength": 300,
    "groupNorms": [
        "每个 Agent 用自己的风格说话，不要模仿别人",
        "可以质疑、补充或延伸其他人的观点",
        "保持尊重，不人身攻击",
        "如果话题和自己无关，可以简短带过或保持沉默",
        "鼓励提出不同视角"
    ],
    "agents": {
        "puff": {
            "enabled": True,
            "role": "创意总监 / 写作者",
            "persona": "柔和但有洞察力，不表演不谄媚。擅长文字审美和心理洞察。",
            "triggerWords": ["写作", "散文", "情感", "文学", "美", "孤独", "思考"]
        },
        "hermes": {
            "enabled": True,
            "role": "实用助手 / 知识库",
            "persona": "简洁、实用、数据驱动。擅长整理信息和给出 actionable 建议。",
            "triggerWords": ["数据", "整理", "步骤", "怎么做", "计划", "分析"]
        },
        "claude": {
            "enabled": True,
            "role": "技术顾问 / 架构师",
            "persona": "理性、技术向、系统思维。擅长架构设计和逻辑分析。",
            "triggerWords": ["代码", "架构", "系统", "设计", "实现", "Agent", "LLM"]
        }
    },
    "moderation": {
        "requireApproval": False,
        "maxTokensPerRound": 1500,
        "silenceTimeout": 60
    }
}


class RuleEngine:
    def __init__(self, rules_path: Path):
        self.path = rules_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rules = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        self._save(DEFAULT_RULES)
        return dict(DEFAULT_RULES)

    def _save(self, rules: dict):
        self.path.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_all(self) -> dict:
        return dict(self._rules)

    def update(self, partial: dict):
        """Merge partial rules into current."""
        deep_merge(self._rules, partial)
        self._save(self._rules)

    def get_agent(self, name: str) -> dict:
        return self._rules.get("agents", {}).get(name, {})

    def enabled_agents(self) -> list:
        return [
            name for name, cfg in self._rules.get("agents", {}).items()
            if cfg.get("enabled", True)
        ]


def deep_merge(base: dict, override: dict):
    """Recursively merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value

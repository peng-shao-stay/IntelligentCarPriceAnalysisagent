"""
Helpers for building history-aware agent context.
"""

from __future__ import annotations

from typing import Dict, List


def normalize_history(history: List[Dict] = None) -> List[Dict]:
    if not history:
        return []

    normalized = []
    for item in history:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if content:
            normalized.append({"role": role, "content": content})
    return normalized


def build_conversation_messages(
    history: List[Dict] = None,
    current_message: str = "",
    max_messages: int = 6,
) -> List[Dict]:
    normalized = normalize_history(history[-max_messages:] if history else history)
    current_message = (current_message or "").strip()

    if current_message:
        if not normalized or normalized[-1]["role"] != "user" or normalized[-1]["content"] != current_message:
            normalized.append({"role": "user", "content": current_message})
    return normalized


def summarize_history(history: List[Dict] = None, max_items: int = 4) -> str:
    normalized = normalize_history(history[-max_items:] if history else history)
    if not normalized:
        return "无历史上下文。"

    lines = []
    for item in normalized:
        speaker = "用户" if item["role"] == "user" else "助手"
        content = item["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def format_tool_payload(payload, max_items: int = 3) -> str:
    """Legacy fallback formatter — prefer ResponseFormatter for intent-aware formatting."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        lines = []
        for key, value in payload.items():
            if isinstance(value, (list, dict)):
                continue
            lines.append(f"- {key}: {value}")
        return "\n".join(lines) if lines else str(payload)
    if isinstance(payload, list):
        lines = []
        for item in payload[:max_items]:
            if isinstance(item, dict):
                lines.append(", ".join(f"{k}={v}" for k, v in item.items()))
            else:
                lines.append(str(item))
        return "\n".join(f"- {line}" for line in lines)
    return str(payload)

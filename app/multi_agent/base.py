"""
Agent 基类 — 多 Agent 协作
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class BaseAgent:
    """所有 Agent 的基类。"""

    name: str = "base"

    def __init__(self, llm_service=None, providers=None):
        self.llm_service = llm_service
        self.providers = providers


class AgentResult:
    """Agent 执行结果。"""

    def __init__(self, success: bool, data: Any = None, error: str = ""):
        self.success = success
        self.data = data or {}
        self.error = error

    def __bool__(self):
        return self.success

    @staticmethod
    def ok(data: Any = None) -> "AgentResult":
        return AgentResult(True, data)

    @staticmethod
    def fail(error: str = "") -> "AgentResult":
        return AgentResult(False, error=error)

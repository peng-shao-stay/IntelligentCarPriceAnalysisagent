"""
Tool registry for the agent runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolExecutionResult:
    tool_name: str
    success: bool
    payload: Any
    summary: str


@dataclass
class AgentTool:
    """A tool that the agent can call.

    Attributes:
        name: Unique tool identifier (e.g., "car_price")
        description: Human-readable description for prompt injection
        intent: The intent category this tool handles (car_price, car_compare, etc.)
        handler: Callable that executes the tool
        keywords: Extra keywords used for intent matching beyond the name
    """
    name: str
    description: str
    intent: str
    handler: Callable[[str, Optional[List[Dict]]], ToolExecutionResult]
    keywords: List[str] = field(default_factory=list)


class ToolRegistry:
    """Thread-safe registry of AgentTools with intent-based and name-based lookup."""

    def __init__(self):
        self._tools: Dict[str, AgentTool] = {}       # intent → tool
        self._by_name: Dict[str, AgentTool] = {}      # name → tool

    def register(self, tool: AgentTool) -> None:
        """Register a tool by intent and name."""
        self._tools[tool.intent] = tool
        self._by_name[tool.name] = tool

    def get_by_intent(self, intent: str) -> Optional[AgentTool]:
        """Look up a tool by its intent category."""
        return self._tools.get(intent)

    def get_by_name(self, name: str) -> Optional[AgentTool]:
        """Look up a tool by its name."""
        return self._by_name.get(name)

    def list_tools(self) -> List[AgentTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def execute(
        self,
        intent: str,
        message: str,
        history: Optional[List[Dict]] = None,
    ) -> ToolExecutionResult:
        """Execute the tool registered for the given intent."""
        tool = self.get_by_intent(intent)
        if tool is None:
            raise KeyError(f"No tool registered for intent: {intent}")
        return tool.handler(message, history)

    def get_tool_descriptions_for_prompt(self) -> List[str]:
        """Return a list of tool descriptions suitable for prompt injection."""
        return [
            f"- **{t.name}**: {t.description}"
            for t in self.list_tools()
        ]

    @property
    def tool_count(self) -> int:
        return len(self._tools)

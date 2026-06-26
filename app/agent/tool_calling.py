"""
Function-calling agent loop.

Instead of keyword matching + button toggle, the LLM chooses:
  - get_web_data(query)    → real-time web search via DuckDuckGo
  - search_knowledge(query) → local RAG knowledge base
  - direct answer           → use training knowledge only

Architecture:
  1. LLM receives user message + tool definitions
  2. LLM decides: answer directly, or call tool(s) once
  3. If tool calls → execute ALL in parallel → feed results back
  4. LLM synthesizes final answer (no more tools allowed)

This is a 2-round agent — search once, synthesize once. No endless looping.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Callable, Dict, List, Optional

from app.core.logging import logger
from app.agent.prompts import SYSTEM_PROMPT

MAX_TOOL_ROUNDS = 2       # round 1: search, round 2: synthesize (no tools)
TOOL_TIMEOUT_SECONDS = 12  # per-tool execution timeout


class ToolCallingAgent:
    """Agent that uses LLM function calling to decide between web search, RAG, and direct answer."""

    def __init__(
        self,
        llm_service,
        toolset=None,
        db_session_factory: Optional[Callable] = None,
    ):
        self.llm_service = llm_service
        self.db_session_factory = db_session_factory
        self._toolset = toolset

    @property
    def toolset(self):
        if self._toolset is None:
            from app.agent.tools.function_tools import FunctionToolset
            self._toolset = FunctionToolset(self.db_session_factory)
        return self._toolset

    def process(
        self,
        message: str,
        history: List[Dict] = None,
        web_search_enabled: bool = True,
    ) -> Dict:
        """Process a user message with function calling.

        Returns dict with:
          - reply: str      → the final text response
          - tool_calls: list → which tools were called
        """
        history = history or []
        tools = self.toolset.all
        called_tools = []

        if not web_search_enabled:
            tools = [self.toolset.search_knowledge]

        messages = self._build_initial_messages(message, history, web_search_enabled)

        # ── Agent loop (max 2 rounds) ──────────────────────────
        for round_idx in range(MAX_TOOL_ROUNDS):
            is_last_round = (round_idx == MAX_TOOL_ROUNDS - 1)

            # On the last round, strip tools — force the LLM to synthesize
            active_tools = None if is_last_round else tools

            try:
                response = self.llm_service.chat_with_tools(
                    messages=messages,
                    tools=active_tools or [],
                    system_prompt=SYSTEM_PROMPT,
                )
            except Exception as exc:
                logger.error(f"ToolCallingAgent: LLM error at round {round_idx}: {exc}")
                return {
                    "reply": f"抱歉，AI 服务暂时不可用。（{exc}）",
                    "tool_calls": called_tools,
                }

            # No tool calls → final response (or tools stripped on last round)
            if not response.has_tool_calls:
                reply = response.content or self._empty_fallback()
                return {"reply": reply, "tool_calls": called_tools}

            # ── Execute tool calls in parallel ─────────────────
            logger.info(
                f"ToolCallingAgent round {round_idx}: "
                f"{len(response.tool_calls)} tool call(s)"
            )

            assistant_msg = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                assistant_msg["tool_calls"] = response.tool_calls
            messages.append(assistant_msg)

            # Execute ALL tool calls concurrently
            tool_results = self._execute_tools_parallel(response.tool_calls)

            for tc, result in zip(response.tool_calls, tool_results):
                func = tc.get("function", {})
                tool_name = func.get("name", "?")
                try:
                    tool_args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                called_tools.append({"name": tool_name, "args": tool_args})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                })

        # Should not reach here (last round has no tools), but safety:
        return {"reply": self._empty_fallback(), "tool_calls": called_tools}

    # ── Internal ────────────────────────────────────────────────

    def _build_initial_messages(
        self,
        message: str,
        history: List[Dict],
        web_search_enabled: bool,
    ) -> List[Dict]:
        from app.agent.context import summarize_history

        context = summarize_history(history)
        mode_line = (
            "【联网搜索已开启】如需实时数据可调用 get_web_data"
            if web_search_enabled
            else "【本地模式】使用训练知识作答，可调用 search_knowledge 查知识库"
        )

        return [{"role": "user", "content": f"{mode_line}\n\n{message}"}]

    def _execute_tools_parallel(self, tool_calls: list) -> List[str]:
        """Execute multiple tool calls concurrently with timeout.

        Returns a list of result strings in the same order as tool_calls.
        """
        if len(tool_calls) == 1:
            # Single tool — no need for thread pool
            tc = tool_calls[0]
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            return [self._execute_tool(name, args)]

        # Multiple tools — run concurrently
        def _run_one(tc):
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            return self._execute_tool(name, args)

        results = []
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
            futures = [pool.submit(_run_one, tc) for tc in tool_calls]
            for tc, future in zip(tool_calls, futures):
                try:
                    results.append(future.result(timeout=TOOL_TIMEOUT_SECONDS))
                except FuturesTimeoutError:
                    func = tc.get("function", {})
                    name = func.get("name", "?")
                    logger.warning(f"ToolCallingAgent: tool '{name}' timed out after {TOOL_TIMEOUT_SECONDS}s")
                    results.append(f"[超时] 工具 '{name}' 执行超过 {TOOL_TIMEOUT_SECONDS} 秒，已跳过。")
                except Exception as exc:
                    func = tc.get("function", {})
                    name = func.get("name", "?")
                    logger.warning(f"ToolCallingAgent: tool '{name}' failed: {exc}")
                    results.append(f"[工具执行失败] {name}: {exc}")

        return results

    def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a single tool by name and return the result string."""
        tools = self.toolset.by_name
        tool = tools.get(name)
        if tool is None:
            return f"[错误] 未知工具: {name}"

        try:
            if hasattr(tool, 'invoke'):
                query = (
                    args.get("query") or
                    args.get("keyword") or
                    args.get("search_query") or
                    str(args)
                )
                result = tool.invoke({"query": query})
                return str(result)
            else:
                return f"[错误] 工具 {name} 不可调用"
        except Exception as exc:
            logger.warning(f"ToolCallingAgent: tool '{name}' failed: {exc}")
            return f"[工具执行失败] {name}: {exc}"

    def _empty_fallback(self) -> str:
        return "抱歉，我暂时无法回答这个问题。请换个方式提问或检查网络连接。"

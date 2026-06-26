"""
LLM 服务 — LangChain + httpx fallback
"""
from __future__ import annotations

import json
from typing import List, Optional

from app.core.config import settings
from app.core.logging import logger

from app.utils.helpers import create_httpx_client

def _get_http_client() -> httpx.Client:
    """Create a fresh httpx client per call (thread-safe)."""
    return create_httpx_client(timeout=120)

# LangChain imports (optional)
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_community.chat_models import ChatOllama
except ImportError:
    ChatOllama = None

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
except ImportError:
    AIMessage = HumanMessage = SystemMessage = ToolMessage = None

# Fallback message types when LangChain is not installed
if AIMessage is None:
    class _FallbackMsg:
        def __init__(self, content: str): self.content = content
        def __repr__(self): return f"{type(self).__name__}({self.content!r})"

    class SystemMessage(_FallbackMsg):
        type = "system"

    class HumanMessage(_FallbackMsg):
        type = "user"

    class AIMessage(_FallbackMsg):
        type = "assistant"

    class ToolMessage(_FallbackMsg):
        type = "tool"
        def __init__(self, content: str, tool_call_id: str = ""):
            super().__init__(content)
            self.tool_call_id = tool_call_id


# ── httpx fallback backends ─────────────────────────────────

class _HttpBackend:
    """纯 httpx 后端，兼容 OpenAI API（DeepSeek 等）。"""

    def __init__(self, model: str, base_url: str, api_key: str = None,
                 temperature: float = 0.7, max_tokens: int = 2000):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, messages: list, tools: list = None) -> _ContentResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": _build_openai_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = _serialize_tools(tools)
            payload["tool_choice"] = "auto"
        resp = _get_http_client().post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        tool_calls = msg.get("tool_calls", [])
        return _ContentResponse(content=msg.get("content") or "", tool_calls=tool_calls)


class _OllamaHttpBackend:
    """纯 httpx 后端，兼容 Ollama API。"""

    def __init__(self, model: str, base_url: str, temperature: float = 0.7):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def invoke(self, messages: list, tools: list = None) -> _ContentResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": _message_role(m), "content": m.content} for m in messages],
            "options": {"temperature": self.temperature},
            "stream": False,
        }
        # Ollama native tool support (v0.3+)
        if tools:
            payload["tools"] = _serialize_tools(tools)
        resp = _get_http_client().post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        return _ContentResponse(content=msg.get("content", "") or "", tool_calls=tool_calls)


class _ContentResponse:
    """Thin wrapper providing a .content attribute for LLM responses."""
    def __init__(self, content: str, tool_calls: list = None):
        self.content = content
        self.tool_calls = tool_calls or []

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


def _message_role(msg) -> str:
    """Map a message object to an OpenAI/Ollama role string via its .type attribute."""
    role = getattr(msg, 'type', None)
    if role == 'system':
        return 'system'
    if role == 'assistant' or role == 'ai':
        return 'assistant'
    if role == 'tool':
        return 'tool'
    return 'user'


def _message_to_openai_dict(msg) -> dict:
    """Convert a LangChain-style message to an OpenAI-compatible dict.
    Handles AIMessage with tool_calls and ToolMessage with tool_call_id.
    """
    role = _message_role(msg)
    entry: dict = {"role": role, "content": msg.content or ""}

    # Carry tool_call_id for ToolMessages
    tc_id = getattr(msg, 'tool_call_id', None)
    if tc_id:
        entry["tool_call_id"] = tc_id

    # Carry tool_calls for AIMessages that request tools
    tc_list = getattr(msg, 'tool_calls', None)
    if tc_list:
        # Convert LangChain ToolCall objects to OpenAI dict format if needed
        converted = []
        for tc in tc_list:
            if isinstance(tc, dict):
                converted.append(tc)
            elif hasattr(tc, 'name'):
                converted.append({
                    "id": getattr(tc, 'id', ''),
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": getattr(tc, 'args', '{}') if hasattr(tc, 'args') else '{}',
                    },
                })
        entry["tool_calls"] = converted

    return entry


def _build_openai_messages(messages: list) -> list:
    """Convert a list of LangChain messages to OpenAI dict format."""
    return [_message_to_openai_dict(m) for m in messages]


def _serialize_tools(tools: list) -> list:
    """Convert LangChain tool objects to OpenAI function-calling format."""
    result = []
    for t in tools:
        name = getattr(t, 'name', str(t))
        description = getattr(t, 'description', '')
        # Build JSON Schema from args_schema if available
        args_schema = getattr(t, 'args_schema', None)
        if args_schema is not None:
            parameters = _pydantic_to_json_schema(args_schema)
        else:
            parameters = {"type": "object", "properties": {}, "required": []}
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        })
    return result


def _pydantic_to_json_schema(model) -> dict:
    """Convert a Pydantic v2 model to JSON Schema dict."""
    try:
        schema = model.model_json_schema()
        return {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }
    except Exception:
        return {"type": "object", "properties": {}, "required": []}


# ── LLM Service ─────────────────────────────────────────────

class LLMService:
    """LLM service with dual backend (ChatOpenAI + ChatOllama) + httpx fallback."""

    def __init__(self):
        self.primary_llm = None
        self.assistant_llm = None
        self.default_model = settings.DEFAULT_MODEL or "primary"
        self._init_backends()

    def _init_backends(self):
        self.primary_llm = self._build_primary()
        self.assistant_llm = self._build_assistant()
        parts = []
        if self.primary_llm is not None:
            parts.append(f"Primary: {settings.DEEPSEEK_MODEL}")
        if self.assistant_llm is not None:
            parts.append(f"Assistant: {settings.OLLAMA_MODEL}")
        logger.info(f"LLM initialized. {' | '.join(parts) if parts else 'No backends'}")

    def _build_primary(self):
        if not settings.API_KEY:
            return None
        # Try LangChain ChatOpenAI first
        if ChatOpenAI is not None:
            try:
                return ChatOpenAI(
                    model=settings.DEEPSEEK_MODEL,
                    temperature=settings.TEMPERATURE,
                    max_tokens=settings.MAX_TOKENS,
                    openai_api_key=settings.API_KEY,
                    openai_api_base=settings.DEEPSEEK_API_BASE_URL,
                    http_client=_get_http_client(),
                )
            except Exception as exc:
                logger.warning(f"ChatOpenAI init failed: {exc}")
        # httpx fallback
        logger.info(f"Using httpx fallback for primary: {settings.DEEPSEEK_MODEL}")
        return _HttpBackend(
            model=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_API_BASE_URL,
            api_key=settings.API_KEY,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )

    def _build_assistant(self):
        if not settings.OLLAMA_BASE_URL:
            return None
        # Use httpx backend directly — LangChain ChatOllama has HTTP/2 issues
        logger.info(f"Using httpx backend for assistant: {settings.OLLAMA_MODEL}")
        return _OllamaHttpBackend(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.TEMPERATURE,
        )

    def reinitialize(self):
        """Rebuild backends from current settings (called after config change)."""
        self._init_backends()

    @property
    def is_available(self) -> bool:
        return self.primary_llm is not None or self.assistant_llm is not None

    def get_status(self) -> dict:
        return {
            "primary_available": self.primary_llm is not None,
            "assistant_available": self.assistant_llm is not None,
            "default_model": self.default_model,
            "primary_model": settings.DEEPSEEK_MODEL,
            "assistant_model": settings.OLLAMA_MODEL,
        }

    def set_model(self, model_type: str = "primary"):
        if model_type not in {"primary", "assistant"}:
            raise ValueError(f"Unknown model type: {model_type}")
        self.default_model = model_type
        logger.info(f"Switched LLM default to {model_type}")

    def _resolve_backend(self, model_type: Optional[str] = None):
        name = model_type or self.default_model or "primary"
        if name == "assistant" and self.assistant_llm is not None:
            return self.assistant_llm
        return self.primary_llm or self.assistant_llm

    def _get_fallback_backend(self, model_type: Optional[str] = None):
        """Return the other backend for fallback on failure."""
        name = model_type or self.default_model or "primary"
        if name == "primary" and self.assistant_llm is not None:
            return self.assistant_llm
        if name == "assistant" and self.primary_llm is not None:
            return self.primary_llm
        return None

    # ── Message conversion ──────────────────────────────────

    @staticmethod
    def _to_langchain_messages(
        messages: List[dict],
        system_prompt: Optional[str] = None,
        include_tool_calls: bool = False,
    ) -> list:
        """Convert dict messages to LangChain message objects.

        Args:
            messages: List of {"role": str, "content": str, ...} dicts.
            system_prompt: Optional system prompt to prepend.
            include_tool_calls: If True, handle tool role and tool_calls on
                assistant messages (for function calling).

        Returns list of LangChain message objects.
        """
        result = []
        if system_prompt:
            result.append(SystemMessage(content=system_prompt))
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                ai_msg = AIMessage(content=content)
                if include_tool_calls:
                    tc_list = msg.get("tool_calls")
                    if tc_list:
                        lc_tc = []
                        for tc in tc_list:
                            func = tc.get("function", {})
                            args = func.get("arguments", "{}")
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    args = {}
                            lc_tc.append({
                                "name": func.get("name", ""),
                                "args": args,
                                "id": tc.get("id", ""),
                            })
                        ai_msg.tool_calls = lc_tc
                result.append(ai_msg)
            elif role == "tool" and include_tool_calls:
                tc_id = msg.get("tool_call_id", "")
                result.append(ToolMessage(content=content, tool_call_id=tc_id))
        return result

    # ── Public chat methods ──────────────────────────────────

    def chat(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> str:
        backend = self._resolve_backend(model_type=model_type)
        if backend is None:
            raise RuntimeError("No LLM backend available. Configure API_KEY or Ollama.")

        langchain_msgs = self._to_langchain_messages(messages, system_prompt)

        try:
            response = backend.invoke(langchain_msgs)
            logger.info("LLM response generated")
            return response.content
        except Exception as exc:
            fallback = self._get_fallback_backend(model_type)
            if fallback is not None:
                logger.warning(f"LLM backend failed ({exc}), trying fallback...")
                response = fallback.invoke(langchain_msgs)
                logger.info("LLM fallback response generated")
                return response.content
            raise

    # ── Function Calling ──────────────────────────────────────

    def chat_with_tools(
        self,
        messages: List[dict],
        tools: list,
        system_prompt: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> _ContentResponse:
        """One round of tool-capable chat. Returns response with content and/or tool_calls.

        Does NOT run the agent loop — caller drives tool execution and feeds results back.
        """
        backend = self._resolve_backend(model_type=model_type)
        if backend is None:
            raise RuntimeError("No LLM backend available. Configure API_KEY or Ollama.")

        langchain_msgs = self._to_langchain_messages(
            messages, system_prompt, include_tool_calls=True,
        )

        try:
            response = self._invoke_with_tools(backend, langchain_msgs, tools)
            logger.info(
                f"LLM tool-chat: content={bool(response.content)}, "
                f"tool_calls={len(response.tool_calls)}"
            )
            return response
        except Exception as exc:
            fallback = self._get_fallback_backend(model_type)
            if fallback is not None:
                logger.warning(f"LLM tool-chat backend failed ({exc}), trying fallback...")
                try:
                    return self._invoke_with_tools(fallback, langchain_msgs, tools)
                except Exception as exc2:
                    logger.warning(f"LLM tool-chat fallback also failed: {exc2}")
                    raise exc
            raise

    def _invoke_with_tools(self, backend, messages: list, tools: list) -> _ContentResponse:
        """Invoke a backend with tools, normalizing the response to _ContentResponse.

        Handles both LangChain ChatOpenAI (needs bind_tools) and httpx backends
        (accept tools parameter directly).
        """
        is_langchain = (
            ChatOpenAI is not None
            and isinstance(backend, ChatOpenAI)
        )

        if is_langchain:
            # ChatOpenAI: bind tools then invoke
            model_with_tools = backend.bind_tools(tools)
            ai_msg = model_with_tools.invoke(messages)
            # Normalize AIMessage → _ContentResponse
            content = ai_msg.content or ""
            tool_calls_raw = getattr(ai_msg, 'tool_calls', []) or []
            # Convert LangChain ToolCall objects to dicts for consistent handling
            tool_calls = []
            for tc in tool_calls_raw:
                if isinstance(tc, dict):
                    tc_id = tc.get("id", "")
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                else:
                    tc_id = getattr(tc, 'id', '')
                    tc_name = getattr(tc, 'name', '')
                    tc_args = getattr(tc, 'args', {})
                # Serialize args to JSON string (matching OpenAI API format)
                args_str = json.dumps(tc_args, ensure_ascii=False) if isinstance(tc_args, dict) else str(tc_args)
                tool_calls.append({
                    "id": tc_id,
                    "type": "function",
                    "function": {
                        "name": tc_name,
                        "arguments": args_str,
                    },
                })
            return _ContentResponse(content=content, tool_calls=tool_calls)
        else:
            # httpx backends (_HttpBackend, _OllamaHttpBackend)
            return backend.invoke(messages, tools=tools)


llm_service = LLMService()

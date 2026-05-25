"""
LLM 服务 — LangChain + httpx fallback
"""
from __future__ import annotations

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
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
except ImportError:
    AIMessage = HumanMessage = SystemMessage = None

# Fallback message types when LangChain is not installed
if AIMessage is None:
    class _FallbackMsg:
        def __init__(self, content: str): self.content = content

    class SystemMessage(_FallbackMsg):
        type = "system"

    class HumanMessage(_FallbackMsg):
        type = "user"

    class AIMessage(_FallbackMsg):
        type = "assistant"


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

    def invoke(self, messages: list) -> _ContentResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": _message_role(m), "content": m.content} for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        resp = _get_http_client().post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return _ContentResponse(data["choices"][0]["message"]["content"])


class _OllamaHttpBackend:
    """纯 httpx 后端，兼容 Ollama API。"""

    def __init__(self, model: str, base_url: str, temperature: float = 0.7):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def invoke(self, messages: list) -> _ContentResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": _message_role(m), "content": m.content} for m in messages],
            "options": {"temperature": self.temperature},
            "stream": False,
        }
        resp = _get_http_client().post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return _ContentResponse(data["message"]["content"])


class _ContentResponse:
    """Thin wrapper providing a .content attribute for LLM responses."""
    def __init__(self, content: str):
        self.content = content


def _message_role(msg) -> str:
    """Map a message object to an OpenAI/Ollama role string via its .type attribute."""
    role = getattr(msg, 'type', None)
    if role == 'system':
        return 'system'
    if role == 'assistant' or role == 'ai':
        return 'assistant'
    return 'user'


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

    def chat(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        model_type: Optional[str] = None,
    ) -> str:
        backend = self._resolve_backend(model_type=model_type)
        if backend is None:
            raise RuntimeError("No LLM backend available. Configure API_KEY or Ollama.")

        langchain_msgs = []
        if system_prompt:
            langchain_msgs.append(SystemMessage(content=system_prompt))
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                langchain_msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_msgs.append(AIMessage(content=content))

        response = backend.invoke(langchain_msgs)
        logger.info("LLM response generated")
        return response.content

    def generate_with_tools(
        self,
        prompt: str,
        tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        if tools:
            tool_desc = "\n".join(str(tool) for tool in tools)
            prompt = f"Available tools:\n{tool_desc}\n\n{prompt}"
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
        )


llm_service = LLMService()

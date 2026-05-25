"""
LLM configuration persistence and connection testing service.
Library-agnostic — uses httpx for testing, dotenv for persistence.
"""
from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import Optional

import dotenv
import httpx

from app.core.config import settings
from app.core.logging import logger

_lock = threading.Lock()


def _get_client(timeout: int = 15) -> httpx.Client:
    """Return a fresh httpx.Client for ``with``-block use."""
    from app.utils.helpers import create_httpx_client
    return create_httpx_client(timeout=timeout)


def _get_env_path() -> str:
    """Resolve the project-root .env file path."""
    return str(Path(__file__).resolve().parent.parent.parent / ".env")


# Map frontend field names to env-var keys
_CLOUD_FIELDS = {
    "api_key": "API_KEY",
    "base_url": "DEEPSEEK_API_BASE_URL",
    "model_name": "DEEPSEEK_MODEL",
    "temperature": "TEMPERATURE",
    "max_tokens": "MAX_TOKENS",
}

_LOCAL_FIELDS = {
    "base_url": "OLLAMA_BASE_URL",
    "model_name": "OLLAMA_MODEL",
    "temperature": "TEMPERATURE",
}


def _mask_api_key(key: Optional[str]) -> Optional[str]:
    """Mask an API key for safe display: show first 4 and last 4 chars."""
    if not key:
        return key
    if len(key) <= 8:
        return key[:2] + "****" + key[-2:]
    return key[:4] + "****" + key[-4:]


def _batch_persist(kv_pairs: dict) -> None:
    """Write multiple key=value pairs to .env in a single read+write cycle.

    Values set to ``None`` are removed from .env and os.environ.
    """
    env_path = _get_env_path()
    with _lock:
        current = dotenv.dotenv_values(env_path)
        for k, v in kv_pairs.items():
            if v is None:
                current.pop(k, None)
                os.environ.pop(k, None)
                if hasattr(settings, k):
                    setattr(settings, k, None)
                logger.info(f"LLM config unset: {k}")
            else:
                current[k] = v
                os.environ[k] = v
                if hasattr(settings, k):
                    setattr(settings, k, v)
                suffix = f"{v[:20]}..." if len(v) > 20 else v
                logger.info(f"LLM config persisted: {k}={suffix}")
        with open(env_path, 'w', encoding='utf-8') as f:
            for k, v in current.items():
                if v:
                    escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                    if any(c in escaped for c in (' ', '#', '=')):
                        escaped = f'"{escaped}"'
                    f.write(f"{k}={escaped}\n")
                else:
                    f.write(f"{k}=\n")


def _unset(key: str) -> None:
    """Remove a key from .env and os.environ."""
    _batch_persist({key: None})


def get_current_config() -> dict:
    """Read current LLM settings and return masked config."""
    return {
        "cloud": {
            "api_key": _mask_api_key(settings.API_KEY),
            "base_url": settings.DEEPSEEK_API_BASE_URL,
            "model_name": settings.DEEPSEEK_MODEL,
            "temperature": settings.TEMPERATURE,
            "max_tokens": settings.MAX_TOKENS,
        },
        "local": {
            "base_url": settings.OLLAMA_BASE_URL,
            "model_name": settings.OLLAMA_MODEL,
            "temperature": settings.TEMPERATURE,
        },
        "default_model": settings.DEFAULT_MODEL or "primary",
    }


def update_config(updates: dict) -> dict:
    """Persist LLM config changes and reinitialize the runtime LLM service.

    `updates` is a dict that may contain ``cloud``, ``local``, and
    ``default_model`` keys, each optional.
    """
    cloud = updates.get("cloud") or {}
    local = updates.get("local") or {}
    default_model = updates.get("default_model")

    # Collect all env changes into a single dict, then write .env once
    env_updates = {}

    for field, env_key in _CLOUD_FIELDS.items():
        if field in cloud and cloud[field] is not None and cloud[field] != "":
            env_updates[env_key] = str(cloud[field])
        elif field == "api_key" and field in cloud and cloud[field] == "":
            env_updates[env_key] = None

    for field, env_key in _LOCAL_FIELDS.items():
        if field in local and local[field] is not None and local[field] != "":
            env_updates[env_key] = str(local[field])

    if default_model:
        env_updates["DEFAULT_MODEL"] = default_model

    if env_updates:
        _batch_persist(env_updates)
        _reinitialize_llm()

    return get_current_config()


def switch_model(model_type: str) -> dict:
    """Switch the default model between 'primary' and 'assistant'."""
    _batch_persist({"DEFAULT_MODEL": model_type})
    # Only update routing, no need to rebuild backends
    try:
        from app.services.llm_service import llm_service
        llm_service.default_model = model_type
    except Exception:
        pass
    return {"default_model": model_type}


def test_connection(backend: str, api_key: str = None,
                    base_url: str = None, model_name: str = None) -> dict:
    """Test connection to the specified LLM backend using httpx."""
    if backend == "cloud":
        effective_key = api_key or settings.API_KEY
        result = _test_cloud(effective_key,
                           base_url or settings.DEEPSEEK_API_BASE_URL,
                           model_name or settings.DEEPSEEK_MODEL)
        result["key_source"] = "provided" if api_key else "stored"
        return result
    return _test_local(base_url or settings.OLLAMA_BASE_URL,
                       model_name or settings.OLLAMA_MODEL)


def _test_cloud(api_key: str, base_url: str, model_name: str) -> dict:
    """Test a DeepSeek-compatible chat completion endpoint."""
    if not api_key:
        return {"success": False, "latency_ms": 0,
                "message": "API Key 未配置", "model_name": model_name}

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hi, reply with just 'ok'."}],
        "max_tokens": 5,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    t0 = time.perf_counter()
    try:
        with _get_client(timeout=15) as client:
            resp = client.post(url, json=payload, headers=headers)
        latency = round((time.perf_counter() - t0) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            actual_model = data.get("model", model_name)
            return {"success": True, "latency_ms": latency,
                    "message": "连接成功", "model_name": actual_model}
        if resp.status_code == 401:
            return {"success": False, "latency_ms": latency,
                    "message": "API Key 无效 (401 Unauthorized)", "model_name": model_name}
        if resp.status_code == 404:
            return {"success": False, "latency_ms": latency,
                    "message": f"模型 '{model_name}' 不存在或端点错误 (404)", "model_name": model_name}
        body = resp.text[:300]
        return {"success": False, "latency_ms": latency,
                "message": f"HTTP {resp.status_code}: {body}", "model_name": model_name}
    except httpx.ConnectError:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "latency_ms": latency,
                "message": f"无法连接到 {base_url}，请检查 Base URL 和网络", "model_name": model_name}
    except httpx.TimeoutException:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "latency_ms": latency,
                "message": "连接超时，请检查网络或增加超时时间", "model_name": model_name}
    except Exception as exc:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "latency_ms": latency,
                "message": f"连接测试异常: {exc}", "model_name": model_name}


def _test_local(base_url: str, model_name: str) -> dict:
    """Test an Ollama endpoint by checking /api/tags for the model."""
    url = f"{base_url.rstrip('/')}/api/tags"

    t0 = time.perf_counter()
    try:
        with _get_client(timeout=10) as client:
            resp = client.get(url)
        latency = round((time.perf_counter() - t0) * 1000, 1)

        if resp.status_code != 200:
            return {"success": False, "latency_ms": latency,
                    "message": f"Ollama 返回 HTTP {resp.status_code}，请确认服务已启动",
                    "model_name": model_name}

        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        if model_name in models:
            return {"success": True, "latency_ms": latency,
                    "message": f"模型 '{model_name}' 已在 Ollama 中可用", "model_name": model_name}
        available = ", ".join(models[:5]) if models else "无"
        return {"success": False, "latency_ms": latency,
                "message": f"模型 '{model_name}' 未找到。可用模型: {available}",
                "model_name": model_name}
    except httpx.ConnectError:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "latency_ms": latency,
                "message": f"无法连接到 {base_url}，请确认 Ollama 已启动",
                "model_name": model_name}
    except httpx.TimeoutException:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "latency_ms": latency,
                "message": "连接超时，请检查网络或增加超时时间",
                "model_name": model_name}
    except Exception as exc:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "latency_ms": latency,
                "message": f"连接测试异常: {exc}", "model_name": model_name}


def _reinitialize_llm() -> None:
    """Trigger runtime LLM service reinitialization if the singleton is available."""
    try:
        from app.services.llm_service import llm_service
        if hasattr(llm_service, "reinitialize"):
            llm_service.reinitialize()
            logger.info("LLM service reinitialized after config change")
    except Exception as exc:
        logger.warning(f"LLM reinitialization skipped: {exc}")

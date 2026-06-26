# -*- coding: utf-8 -*-
"""
End-to-end test: LLM function calling with web search + knowledge base tools.
"""
from __future__ import annotations

import json
import sys

# Add project root
sys.path.insert(0, ".")

from app.agent.tool_calling import ToolCallingAgent
from app.services.llm_service import llm_service


def test_function_calling():
    print("=" * 60)
    print("  Function Calling E2E Test")
    print("=" * 60)

    if not llm_service.is_available:
        print("[SKIP] No LLM backend available")
        return

    print(f"[OK] LLM available: {llm_service.get_status()}")

    agent = ToolCallingAgent(llm_service=llm_service)

    test_queries = [
        ("联网模式-搜索", "特斯拉 Model 3 最新价格是多少？", True),
        ("联网模式-天气", "今天天气怎么样？", True),
        ("本地模式-对话", "你好，介绍一下你自己", False),
    ]

    for label, query, web_search in test_queries:
        print(f"\n{'─' * 50}")
        print(f">>> [{label}] {query}")
        print(f"    web_search={web_search}")
        print(f"{'─' * 50}")

        try:
            result = agent.process(message=query, history=[], web_search_enabled=web_search)
            reply = result.get("reply", "")
            called = result.get("tool_calls", [])

            print(f"\n[Tools called]: {[c['name'] for c in called] if called else 'none'}")
            print(f"[Response preview]: {reply[:300]}")
            if len(reply) > 300:
                print(f"    ... ({len(reply)} chars total)")

        except Exception as exc:
            print(f"\n[FAIL]: {exc}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_function_calling()

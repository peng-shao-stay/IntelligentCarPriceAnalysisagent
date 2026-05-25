"""
Tests for context helpers.
"""
from __future__ import annotations

import unittest

from app.agent.context import build_conversation_messages, summarize_history


class TestContextHelpers(unittest.TestCase):
    def test_build_conversation_messages_deduplicates_current_user_message(self):
        history = [
            {"role": "user", "content": "特斯拉 Model 3 多少钱"},
        ]

        messages = build_conversation_messages(history, "特斯拉 Model 3 多少钱")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "特斯拉 Model 3 多少钱")

    def test_build_conversation_messages_appends_new_message(self):
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，我能帮你看车价。"},
        ]

        messages = build_conversation_messages(history, "帮我查一下 Model 3")

        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[-1]["content"], "帮我查一下 Model 3")

    def test_summarize_history_formats_roles(self):
        history = [
            {"role": "user", "content": "我想买电车"},
            {"role": "assistant", "content": "预算大概多少？"},
        ]

        summary = summarize_history(history)

        self.assertIn("用户: 我想买电车", summary)
        self.assertIn("助手: 预算大概多少？", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)

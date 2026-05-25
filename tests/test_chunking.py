"""
Unit tests for semantic chunking engine (Module 2 RAG refactor).
"""
from __future__ import annotations

import unittest

from app.utils.helpers import (
    estimate_tokens,
    split_by_sections,
    semantic_chunk,
    chunk_text,
)


class TestEstimateTokens(unittest.TestCase):
    def test_pure_chinese(self):
        n = estimate_tokens("这是一段纯中文文本测试")
        self.assertGreater(n, 0)

    def test_pure_english(self):
        n = estimate_tokens("This is a pure English sentence")
        self.assertGreater(n, 0)

    def test_mixed_cjk_ascii(self):
        n = estimate_tokens("特斯拉 Model 3 价格 23.19 万起")
        self.assertGreater(n, 5)

    def test_empty(self):
        self.assertEqual(estimate_tokens(""), 0)


class TestSplitBySections(unittest.TestCase):
    def test_markdown_headings_split(self):
        text = "# 价格\n售价 23.19 万\n# 续航\nCLTC 续航 606 km"
        sections = split_by_sections(text)
        self.assertGreaterEqual(len(sections), 2)
        self.assertTrue(any("价格" in s for s in sections))
        self.assertTrue(any("续航" in s for s in sections))

    def test_car_domain_boundaries(self):
        text = (
            "特斯拉 Model 3 是一款热门电动车。\n\n"
            "价格方面，起售价 23.19 万元。\n\n"
            "续航里程为 CLTC 606 公里。\n\n"
            "动力性能：零百加速 6.1 秒。"
        )
        sections = split_by_sections(text)
        self.assertGreaterEqual(len(sections), 3)

    def test_no_boundaries_fallback(self):
        text = "这是一段没有任何语义边界的简单文本。"
        sections = split_by_sections(text)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0], text)

    def test_empty_text(self):
        self.assertEqual(split_by_sections(""), [""])


class TestSemanticChunk(unittest.TestCase):
    def setUp(self):
        self.review = (
            "# 特斯拉 Model 3 详细评测\n\n"
            "## 价格\n"
            "特斯拉 Model 3 后轮驱动版起售价为 231,900 元，长续航版 271,900 元，"
            "高性能版 335,900 元。各地经销商有一定优惠，具体以当地报价为准。\n\n"
            "## 续航与电池\n"
            "后轮驱动版搭载 60kWh 磷酸铁锂电池，CLTC 续航 606 公里。"
            "长续航版搭载 78.4kWh 三元锂电池，CLTC 续航 713 公里。"
            "支持快充，30 分钟可充至 80%。\n\n"
            "## 动力性能\n"
            "后驱版单电机 194kW/340Nm，零百加速 6.1 秒。"
            "高性能版双电机四驱，最大功率 357kW，零百加速 3.3 秒。\n\n"
            "## 智能驾驶\n"
            "标配 Autopilot 辅助驾驶，包含车道保持、自适应巡航、自动紧急制动。"
            "可选装增强版自动辅助驾驶（EAP）和完全自动驾驶能力（FSD）。\n\n"
            "## 空间与舒适性\n"
            "轴距 2875mm，后排空间充裕。前排座椅支持 12 向电动调节，"
            "带加热功能。全景天幕增加了车内通透感。NVH 表现在同级中优秀。\n\n"
            "## 安全性\n"
            "全车配备 8 个安全气囊，车身采用超高强度钢铝混合结构。"
            "Euro NCAP 碰撞测试获五星评级。主动安全配置丰富。\n\n"
            "## 车机与座舱\n"
            "15 英寸中控触摸屏，搭载 AMD Ryzen 芯片。语音控制功能便捷，"
            "OTA 持续更新。音响系统出色，导航流畅。\n\n"
            "## 外观设计\n"
            "极简主义设计风格，风阻系数 0.23Cd。隐藏式门把手，"
            "无进气格栅前脸，辨识度高。提供多种颜色选择。\n\n"
            "总体来说，特斯拉 Model 3 在 25 万级别电动车市场中具有很强竞争力，"
            "是兼顾品牌、性能和智能化的标杆产品。"
        )

    def test_produces_multiple_chunks(self):
        chunks = semantic_chunk(self.review, max_tokens=200, target_tokens=120, min_tokens=60)
        self.assertGreaterEqual(len(chunks), 3)
        for c in chunks:
            self.assertGreater(len(c), 10)

    def test_chunks_within_token_limit(self):
        chunks = semantic_chunk(self.review, max_tokens=800, target_tokens=500)
        for i, c in enumerate(chunks):
            tokens = estimate_tokens(c)
            self.assertLessEqual(tokens, 800, f"chunk {i} has {tokens} tokens (max 800)")

    def test_overlap_between_chunks(self):
        chunks = semantic_chunk(self.review, overlap_tokens=100)
        if len(chunks) > 1:
            c0_end = chunks[0][-30:]
            c1_start = chunks[1][:30]
            self.assertGreater(len(chunks[1]), 20)

    def test_empty_text(self):
        self.assertEqual(semantic_chunk(""), [])

    def test_short_text_single_chunk(self):
        text = "特斯拉 Model 3 起售价 23.19 万，CLTC 续航 606km。"
        chunks = semantic_chunk(text)
        self.assertEqual(len(chunks), 1)
        self.assertIn("特斯拉", chunks[0])

    def test_custom_token_params(self):
        chunks = semantic_chunk(self.review, target_tokens=400, min_tokens=200, max_tokens=500)
        for i, c in enumerate(chunks):
            tokens = estimate_tokens(c)
            self.assertLessEqual(tokens, 500, f"chunk {i} has {tokens} tokens")


class TestChunkTextBackwardCompat(unittest.TestCase):
    """Verify chunk_text() still works as a semantic_chunk wrapper."""

    def test_returns_chunks(self):
        text = "比亚迪海豹 CLTC 续航 700 公里。价格 17.98 万起。搭载刀片电池。"
        chunks = chunk_text(text, chunk_size=1000, overlap=100)
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0)

    def test_empty_text(self):
        self.assertEqual(chunk_text(""), [])


if __name__ == "__main__":
    unittest.main()

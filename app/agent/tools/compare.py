"""
Car comparison helpers.
"""
from __future__ import annotations

from typing import Dict, List

from app.agent.prompts import CAR_COMPARISON_PROMPT
from app.core.logging import logger
from app.utils.helpers import format_price


def compare_cars(cars: List[Dict], llm_client=None) -> str:
    """Compare multiple cars, using an LLM when available."""
    logger.info(f"Comparing {len(cars)} cars")

    cars_info = "\n".join(
        f"- {car.get('brand', '未知品牌')} {car.get('model', '未知车型')} "
        f"{car.get('version', '')} 价格: "
        f"{format_price(car.get('price', 0), car.get('currency', 'CNY')) if car.get('price') else '暂无'}"
        for car in cars
    )

    if llm_client and getattr(llm_client, "is_available", False):
        prompt = CAR_COMPARISON_PROMPT.format(cars_info=cars_info)
        try:
            return llm_client.chat([{"role": "user", "content": prompt}])
        except Exception as exc:
            logger.warning(f"LLM comparison failed, using fallback summary: {exc}")

    return _build_fallback_comparison(cars)


def calculate_price_difference(car1: Dict, car2: Dict) -> Dict:
    price1 = car1.get("price", 0)
    price2 = car2.get("price", 0)
    diff = price2 - price1
    percentage = (diff / price1 * 100) if price1 > 0 else 0
    return {
        "car1_price": price1,
        "car2_price": price2,
        "absolute_diff": diff,
        "percentage_diff": round(percentage, 2),
    }


def _build_fallback_comparison(cars: List[Dict]) -> str:
    lines = ["已根据当前可用数据整理车型对比："]

    for car in cars:
        name = f"{car.get('brand', '未知品牌')} {car.get('model', '未知车型')}".strip()
        if car.get("price"):
            lines.append(f"- {name} 参考价 {format_price(car['price'], car.get('currency', 'CNY'))}")
        else:
            lines.append(f"- {name} 暂无可靠价格数据")

    if len(cars) >= 2 and cars[0].get("price") and cars[1].get("price"):
        diff = calculate_price_difference(cars[0], cars[1])
        lines.append(
            "两车价差约 "
            f"{format_price(abs(diff['absolute_diff']), cars[0].get('currency', 'CNY'))}。"
        )

    lines.append("如果你愿意，我下一步可以继续按空间、续航、配置或性价比维度细化对比。")
    return "\n".join(lines)

"""
特斯拉爬虫 - 独立爬虫脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.crawler_service import TeslaCrawler
from app.core.logging import logger


def main():
    """主函数"""
    crawler = TeslaCrawler()
    
    logger.info("Starting Tesla price crawler...")
    
    # 获取价格信息
    prices = crawler.get_car_prices()
    
    logger.info(f"Found {len(prices)} car prices")
    
    for car in prices:
        print(f"\n品牌: {car['brand']}")
        print(f"车型: {car['model']}")
        print(f"版本: {car['version']}")
        print(f"价格: ¥{car['price']:,}")
        print(f"来源: {car['source']}")
        print("-" * 50)
    
    return prices


if __name__ == "__main__":
    main()

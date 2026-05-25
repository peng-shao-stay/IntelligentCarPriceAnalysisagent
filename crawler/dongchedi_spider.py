"""
懂车帝爬虫 - 独立爬虫脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.crawler_service import DongchediCrawler
from app.core.logging import logger


def main():
    """主函数"""
    crawler = DongchediCrawler()
    
    logger.info("Starting Dongchedi crawler...")
    
    # 示例:搜索特定车型
    brand = "比亚迪"
    model = "汉"
    
    logger.info(f"Searching for {brand} {model}")
    
    prices = crawler.search_car_price(brand, model)
    
    logger.info(f"Found {len(prices)} results")
    
    for car in prices:
        print(f"\n品牌: {car['brand']}")
        print(f"车型: {car['model']}")
        print(f"版本: {car['version']}")
        print(f"价格: ¥{car['price']:,}")
        print(f"来源: {car['source']}")
        print("-" * 50)
    
    # 获取新闻
    news = crawler.get_latest_news(brand=brand, limit=5)
    
    logger.info(f"Found {len(news)} news articles")
    
    return prices


if __name__ == "__main__":
    main()

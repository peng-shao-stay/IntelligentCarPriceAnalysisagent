"""
Crawler services with optional requests support.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger

try:
    import requests
except ImportError:  # pragma: no cover - exercised only in minimal environments
    requests = None


class CrawlerService:
    """Base crawler service."""

    def __init__(self):
        self.session = None
        if requests is not None:
            self.session = requests.Session()
            self.session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                    )
                }
            )
        logger.info("Crawler service initialized")

    def fetch_page(self, url: str, timeout: int = None) -> Optional[str]:
        if self.session is None:
            logger.warning(f"requests is unavailable, cannot fetch page: {url}")
            return None

        try:
            response = self.session.get(url, timeout=timeout or settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except Exception as exc:  # pragma: no cover - depends on remote requests
            logger.error(f"Failed to fetch {url}: {exc}")
            return None

    def parse_json_response(self, url: str, params: Dict = None) -> Optional[Dict]:
        if self.session is None:
            logger.warning(f"requests is unavailable, cannot fetch JSON: {url}")
            return None

        try:
            response = self.session.get(url, params=params, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - depends on remote requests
            logger.error(f"Failed to fetch JSON from {url}: {exc}")
            return None


class TeslaCrawler(CrawlerService):
    """Simple Tesla crawler stub."""

    def __init__(self):
        super().__init__()
        self.base_url = "https://www.tesla.cn"

    def get_car_prices(self) -> List[Dict]:
        logger.info("Fetching Tesla car prices")
        return [
            {
                "brand": "Tesla",
                "model": "Model 3",
                "version": "后轮驱动版",
                "price": 231900,
                "currency": "CNY",
                "source": "Tesla Official",
                "url": f"{self.base_url}/model3",
            }
        ]


class DongchediCrawler(CrawlerService):
    """Simple Dongchedi crawler stub."""

    def __init__(self):
        super().__init__()
        self.base_url = "https://www.dongchedi.com"

    def search_car_price(self, brand: str, model: str) -> List[Dict]:
        logger.info(f"Searching {brand} {model} on Dongchedi")
        return [
            {
                "brand": brand,
                "model": model,
                "version": "2024款",
                "price": 150000,
                "currency": "CNY",
                "source": "Dongchedi",
                "url": f"{self.base_url}/auto",
            }
        ]

    def get_latest_news(self, brand: str = None, limit: int = 10) -> List[Dict]:
        logger.info(f"Fetching latest news for brand={brand}")
        return []


tesla_crawler = TeslaCrawler()
dongchedi_crawler = DongchediCrawler()

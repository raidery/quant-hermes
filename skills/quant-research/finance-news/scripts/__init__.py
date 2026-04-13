"""
Hermes Finance News — Unified financial news scraper
Supports: EastMoney (eastmoney.com) · WallStreetCN (wallstreetcn.com) · IWenCai (iwencai.com)

Version: 0.2.0
"""

from .scraper import FinanceNewsScraper, NewsItem, ScrapeResult

__all__ = ["FinanceNewsScraper", "NewsItem", "ScrapeResult"]

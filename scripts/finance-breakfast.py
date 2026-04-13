#!/usr/bin/env python3
"""财经早餐 cron runner — 使用 hermes-agent venv"""
import sys
import os

# 使用 hermes-agent 的 venv
VENV_PYTHON = "/home/claw/.hermes/hermes-agent/venv/bin/python3"

# 确保 skill 路径在 sys.path
SKILL_SCRIPTS = "/home/claw/.hermes/skills/quant-research/finance-news/scripts"

def main():
    from datetime import datetime
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    # Import finance-news
    sys.path.insert(0, SKILL_SCRIPTS)
    from scraper import FinanceNewsScraper

    scraper = FinanceNewsScraper()
    items = scraper.fetch_all(sources=["eastmoney", "sina", "iwencai", "cailian"], page_size=20)
    today = datetime.now().strftime("%Y-%m-%d")
    output = scraper.to_markdown(items, title=f"📰 财经早餐 {today}")

    # Print to stdout — cron captures this
    print(output)

if __name__ == "__main__":
    main()

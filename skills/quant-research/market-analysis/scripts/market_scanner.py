"""
大盘快速扫描模块 - Hermes 版本
目标：5秒内并行获取所有核心市场数据

用法：
    from market_scanner import scan_market, format_market_report
    data = scan_market()
    print(format_market_report(data))
"""

import sys, os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 路径：finance-news 的 scraper
SCRAPER_DIR = "/home/claw/.hermes/skills/quant-research/finance-news/scripts"
sys.path.insert(0, SCRAPER_DIR)

import requests
from market_quotes import TencentMarket

TIMEOUT = 8  # 单个API超时（秒）


# ─────────────────────────────────────────────────────────────────────────────
# Part 1: 各数据源获取函数
# ─────────────────────────────────────────────────────────────────────────────

def get_index_data() -> dict:
    """腾讯财经：获取上证/深证/创业板/沪深300指数"""
    try:
        codes = ["sh000001", "sz399001", "sz399006", "sh000300"]
        quotes = TencentMarket.fetch_all(codes=codes)
        result = {}
        for q in quotes:
            key_map = {
                "sh000001": "sh", "sz399001": "sz",
                "sz399006": "cyb", "sh000300": "hs300"
            }
            key = key_map.get(q.symbol)
            if key:
                result[key] = {
                    "name": q.name,
                    "price": q.price,
                    "change": q.change,
                    "change_pct": q.change_pct,
                    "volume": q.volume,
                    "turnover": q.turnover,
                }
        return result
    except Exception as e:
        return {}


def get_us_data() -> dict:
    """腾讯财经：获取美股三大指数"""
    try:
        codes = ["usDJI", "usINX", "usNDX"]
        quotes = TencentMarket.fetch_all(codes=codes)
        result = {}
        for q in quotes:
            key_map = {"usDJI": "dji", "usINX": "inx", "usNDX": "ndx"}
            key = key_map.get(q.symbol)
            if key:
                result[key] = {
                    "name": q.name,
                    "price": q.price,
                    "change": q.change,
                    "change_pct": q.change_pct,
                }
        return result
    except Exception:
        return {}


def get_advance_decline() -> dict:
    """东方财富：获取上涨/下跌家数（市场宽度）"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/ulist.np/get"
            "?fltt=2&invt=2&fields=f1,f2,f3,f4,f12,f14,f15,f16,f17,f18"
            "&secids=1.000001,0.399001,0.399006,1.000300,100.DJI,100.INX,100.NDX"
        )
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.eastmoney.com"
        }, timeout=TIMEOUT)
        data = r.json()
        items = data.get("data", {}).get("diff", [])
        result = {}
        for item in items:
            code = str(item.get("f12", ""))
            name_map = {
                "000001": "上证", "399001": "深证",
                "399006": "创业板", "000300": "沪深300"
            }
            key = name_map.get(code)
            if key:
                result[key] = {
                    "name": item.get("f14", key),
                    "chg_pct": item.get("f3", 0),
                    "close": item.get("f2", 0),
                }
        return result
    except Exception:
        return {}


def get_hot_sectors() -> list[dict]:
    """东方财富：获取今日热门板块（涨幅前10）"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?cb=jQuery&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50"
            "&fields=f1,f2,f3,f4,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f26"
            "&_=1"
        )
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.eastmoney.com"
        }, timeout=TIMEOUT)
        text = r.text
        # JSONP: jQuery({...})
        json_str = text[7:-1] if text.startswith("jQuery") else text
        data = json.loads(json_str)
        items = data.get("data", {}).get("diff", [])
        hot = []
        for item in items[:10]:
            hot.append({
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "lead_stock": item.get("f15", ""),
                "turnover": item.get("f6", 0),
            })
        return hot
    except Exception:
        return []


def get_limit_up_count() -> dict:
    """东方财富：获取涨停/跌停家数"""
    try:
        # 涨停
        url_up = (
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23"
            "&fields=f1,f2,f3,f4,f12,f14&_=1"
        )
        r = requests.get(url_up, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.eastmoney.com"
        }, timeout=TIMEOUT)
        text = r.text
        json_str = text[7:-1] if text.startswith("jQuery") else text
        data = json.loads(json_str)
        up_count = len(data.get("data", {}).get("diff", []))
        return {"limit_up": up_count}
    except Exception:
        return {"limit_up": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: 并行扫描
# ─────────────────────────────────────────────────────────────────────────────

def scan_market() -> dict:
    """
    并行获取所有市场数据，返回结构化字典。
    耗时约 3-5 秒。
    """
    t0 = time.time()
    results = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(get_index_data): "index",
            executor.submit(get_us_data): "us",
            executor.submit(get_hot_sectors): "sectors",
            executor.submit(get_limit_up_count): "limit",
        }

        for future in as_completed(futures, timeout=TIMEOUT + 2):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {}
                print(f"[market_scanner] {key} failed: {e}", file=sys.stderr)

    results["_elapsed"] = round(time.time() - t0, 1)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Part 3: 格式化报告
# ─────────────────────────────────────────────────────────────────────────────

def format_market_report(data: dict) -> str:
    """格式化大盘扫描报告（emoji 纯文本）"""
    index = data.get("index", {})
    us = data.get("us", {})
    sectors = data.get("sectors", [])
    limit = data.get("limit", {})
    elapsed = data.get("_elapsed", 0)

    lines = [
        "📊 大盘快速扫描",
        f"  ⏱ {elapsed}s",
        "",
        "━━ A股指数 ━━",
    ]

    index_icons = {"sh": "上证", "sz": "深证", "cyb": "创业板", "hs300": "沪深300"}
    for key, label in index_icons.items():
        d = index.get(key, {})
        if not d:
            continue
        arrow = "▲" if d["change"] >= 0 else "▼"
        sign = "+" if d["change"] >= 0 else ""
        chg = d["change_pct"]
        lines.append(
            f"  {label:<6} {d['price']:>10,.2f}  {arrow} {sign}{chg:>8.2f}%"
        )

    if us:
        lines.append("")
        lines.append("━━ 美股（昨夜） ━━")
        us_icons = {"dji": "道琼斯", "inx": "标普500", "ndx": "纳指100"}
        for key, label in us_icons.items():
            d = us.get(key, {})
            if not d:
                continue
            arrow = "▲" if d["change"] >= 0 else "▼"
            sign = "+" if d["change"] >= 0 else ""
            chg = d["change_pct"]
            lines.append(
                f"  {label:<6} {d['price']:>10,.2f}  {arrow} {sign}{chg:>8.2f}%"
            )

    if sectors:
        lines.append("")
        lines.append("━━ 热门板块 Top5 ━━")
        for s in sectors[:5]:
            arrow = "▲" if s["change_pct"] >= 0 else "▼"
            sign = "+" if s["change_pct"] >= 0 else ""
            chg = s["change_pct"]
            lines.append(
                f"  {s['name']:<12} {arrow} {sign}{chg:>6.2f}%  领涨: {s.get('lead_stock','')}"
            )

    limit_up = limit.get("limit_up", 0)
    lines.append("")
    lines.append(f"  涨停家数: {limit_up} 家")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    data = scan_market()
    print(format_market_report(data))

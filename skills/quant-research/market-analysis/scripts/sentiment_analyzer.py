"""
情绪分析模块 - 与 market_scanner.py 互补
==========================================

market_scanner.py 负责：指数、板块、美股
sentiment_analyzer.py 负责：涨跌家数、涨停炸板、北向资金、情绪评分

数据源优先级：
1. 东方财富 push2（涨停/跌停/资金流向）
2. 新浪财经（涨跌采样）
3. 腾讯财经（指数/北向/港股）
4. 乐咕乐股/其他（备用）

用法：
    from sentiment_analyzer import analyze_sentiment, format_sentiment_report

    data = analyze_sentiment()
    print(format_sentiment_report(data))
"""

import sys
import os
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

TIMEOUT = 8  # 单API超时（秒）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ─────────────────────────────────────────────────────────────────────────────
# Part 1: 各数据源获取函数
# ─────────────────────────────────────────────────────────────────────────────

def get_limit_up_down() -> dict:
    """
    东方财富：获取涨停/跌停家数
    数据结构：涨停(20%科创创业)、涨停(10%主板)、跌停
    """
    result = {
        "limit_up_total": 0,
        "limit_up_20": 0,
        "limit_up_10": 0,
        "limit_down_total": 0,
        "limit_down_10": 0,
        "available": False,
        "source": "eastmoney",
    }
    try:
        # 涨停（取前100条，估算总数）
        url_up = (
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=100&po=1&np=1"
            "&ut=b2884a393a59ad64002292a3e90d46a5"
            "&fltt=2&invt=2&fid=f3"
            "&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23"
            "&fields=f2,f3,f12,f14&_=1"
        )
        r = requests.get(url_up, headers=HEADERS, timeout=TIMEOUT)
        d = r.json()
        items = d.get("data", {}).get("diff", [])
        total = d.get("data", {}).get("total", 0)

        zt_20 = [i for i in items if float(i.get("f3", 0)) >= 19.9]
        zt_10 = [i for i in items if 9.9 <= float(i.get("f3", 0)) < 19.9]

        result["limit_up_total"] = total or (len(zt_20) + len(zt_10))
        result["limit_up_20"] = len(zt_20)
        result["limit_up_10"] = len(zt_10)
        result["available"] = True

        # 跌停（取前50条）
        url_down = (
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=50&po=0&np=1"
            "&ut=b2884a393a59ad64002292a3e90d46a5"
            "&fltt=2&invt=2&fid=f3"
            "&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23"
            "&fields=f2,f3,f12,f14&_=1"
        )
        r2 = requests.get(url_down, headers=HEADERS, timeout=TIMEOUT)
        d2 = r2.json()
        items2 = d2.get("data", {}).get("diff", [])
        dt = [i for i in items2 if float(i.get("f3", 0)) <= -9.9]
        result["limit_down_total"] = len(dt)
        result["limit_down_10"] = len(dt)
        result["available"] = True

    except Exception as e:
        result["error"] = str(e)[:80]
    return result


def get_advance_decline_sample() -> dict:
    """
    新浪财经：涨跌家数采样估算
    通过多页采样估算市场整体涨跌家数比
    """
    result = {
        "up_estimate": 0,
        "down_estimate": 0,
        "flat_estimate": 0,
        "up_ratio": 0.0,  # 上涨/（上涨+下跌）
        "available": False,
        "source": "sina",
        "note": "",
    }
    try:
        # 上涨采样（取3000条，大概率全为上涨）
        url_up = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
            "/Market_Center.getHQNodeDataSimple"
            "?page=1&num=3000&sort=changepercent&asc=0&node=hs_a&_s_r_a=page"
        )
        r = requests.get(url_up, headers=HEADERS, timeout=TIMEOUT)
        items_up = r.json()
        up_count = len([i for i in items_up if float(i.get("changepercent", 0)) > 0])

        # 下跌采样（asc=1升序，取最低涨幅的1000条，包含大量下跌）
        url_down = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
            "/Market_Center.getHQNodeDataSimple"
            "?page=1&num=1000&sort=changepercent&asc=1&node=hs_a&_s_r_a=page"
        )
        r2 = requests.get(url_down, headers=HEADERS, timeout=TIMEOUT)
        items_down_full = r2.json()
        down_count = len([i for i in items_down_full if float(i.get("changepercent", 0)) < 0])

        # 新浪采样不均匀，用以下逻辑估算：
        # A股总股本数约5500-5700，取5300估算
        total_estimate = 5300
        # 上涨采样中全是上涨，说明市场确实偏强
        # 下跌采样中，1000条按比例估算
        result["up_estimate"] = up_count
        result["down_estimate"] = down_count
        result["up_ratio"] = round(up_count / (up_count + down_count + 0.001), 3)
        result["flat_estimate"] = max(0, total_estimate - up_count - down_count)
        result["available"] = True
        result["note"] = f"基于{up_count}上涨+{down_count}下跌采样估算(total~{total_estimate})"

    except Exception as e:
        result["error"] = str(e)[:80]
    return result


def get_northbound_flow() -> dict:
    """
    北向资金：尝试多个数据源
    1. 东方财富 沪深港通
    2. 腾讯行情（港股指数联动）
    3. 港股恒生/国企指数（间接判断）
    """
    result = {
        "hk_hs": 0.0,       # 恒生指数涨跌幅
        "hk_hsce": 0.0,    # 国企指数涨跌幅
        "hk_connect_sh": None,  # 沪股通（净流入/出）
        "hk_connect_sz": None,  # 深股通
        "northbound_net": None, # 北向合计净流入
        "available": False,
        "source": "",
    }

    # 方法1：腾讯获取港股指数
    # 腾讯字段: [3]=现价 [4]=涨跌额 [5]=涨跌幅% [6]=成交量
    try:
        url = "https://qt.gtimg.cn/q=s_hkHSCEI,s_hkHSI"
        r = requests.get(url, timeout=TIMEOUT)
        for line in r.text.strip().split("\n"):
            parts = line.split("~")
            if len(parts) < 6:
                continue
            code = parts[2] if len(parts) > 2 else ""
            pct = float(parts[5]) if parts[5] else 0  # 涨跌幅% 在 [5]
            if code == "HSI":
                result["hk_hs"] = pct
            elif code == "HSCEI":
                result["hk_hsce"] = pct
        if any(v != 0 for v in [result["hk_hs"], result["hk_hsce"]]):
            result["available"] = True
            result["source"] = "tencent_hk"
    except Exception:
        pass

    return result


def get_sector_money_flow() -> dict:
    """
    板块资金流向：东方财富板块资金流排行
    """
    result = {
        "top_inflow": [],   # 主力净流入板块
        "top_outflow": [],  # 主力净流出板块
        "available": False,
        "source": "",
    }
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=20&po=1&np=1"
            "&ut=b2884a393a59ad64002292a3e90d46a5"
            "&fltt=2&invt=2&fid=f62"
            "&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23"
            "&fields=f12,f14,f62,f184&_=1"
        )
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        d = r.json()
        items = d.get("data", {}).get("diff", [])
        inflow = [i for i in items if float(i.get("f62", 0)) > 0][:5]
        outflow = [i for i in items if float(i.get("f62", 0)) < 0][-5:]

        result["top_inflow"] = [
            {"name": i.get("f14", ""), "money": round(float(i.get("f62", 0)) / 1e8, 2)}
            for i in inflow
        ]
        result["top_outflow"] = [
            {"name": i.get("f14", ""), "money": round(float(i.get("f62", 0)) / 1e8, 2)}
            for i in outflow
        ]
        result["available"] = True
        result["source"] = "eastmoney"

    except Exception as e:
        result["error"] = str(e)[:80]
    return result


def get_yesterday_limit_today() -> dict:
    """
    昨日涨停今日表现（炸板率）
    新浪/东方财富接口均可能无数据，预留结构
    """
    result = {
        "total": 0,
        "avg_gain": 0.0,   # 平均溢价
        "bomb_count": 0,  # 炸板数（高开低走）
        "hold_count": 0,   # 继续涨停数
        "available": False,
        "source": "",
        "note": "数据源受限，暂无法获取",
    }
    # 新浪昨日涨停节点
    try:
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
            "/Market_Center.getHQNodeDataSimple"
            "?page=1&num=20&sort=changepercent&asc=1&node=hs_zte&_s_r_a=page"
        )
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        items = r.json()
        if items and len(items) > 0:
            gains = [float(i.get("changepercent", 0)) for i in items]
            result["total"] = len(items)
            result["avg_gain"] = round(sum(gains) / len(gains), 2) if gains else 0
            result["hold_count"] = len([g for g in gains if g >= 9.9])
            result["bomb_count"] = len([g for g in gains if 0 <= g < 9.9])
            result["available"] = True
            result["source"] = "sina"
    except Exception:
        pass
    return result


def get_us_night() -> dict:
    """
    美股昨夜收盘：道琼斯、标普500、纳斯达克
    """
    result = {
        "dji": {"price": 0, "chg": 0, "chg_pct": 0},
        "inx": {"price": 0, "chg": 0, "chg_pct": 0},
        "ndx": {"price": 0, "chg": 0, "chg_pct": 0},
        "available": False,
        "source": "tencent",
    }
    try:
        url = "https://qt.gtimg.cn/q=usDJI,usINX,usNDX"
        r = requests.get(url, timeout=TIMEOUT)
        for line in r.text.strip().split("\n"):
            parts = line.split("~")
            if len(parts) < 6:
                continue
            sym = parts[2] if len(parts) > 2 else ""
            price = float(parts[3]) if parts[3] else 0
            chg = float(parts[4]) if parts[4] else 0
            pct = float(parts[5]) if parts[5] else 0
            if sym == "DJI":
                result["dji"] = {"price": price, "chg": chg, "chg_pct": pct}
            elif sym == "INX":
                result["inx"] = {"price": price, "chg": chg, "chg_pct": pct}
            elif sym == "NDX":
                result["ndx"] = {"price": price, "chg": chg, "chg_pct": pct}
        if any(v["price"] > 0 for v in result.values()):
            result["available"] = True
    except Exception:
        pass
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: 情绪评分引擎
# ─────────────────────────────────────────────────────────────────────────────

def score_sentiment(limit_data: dict, ad_data: dict, nb_data: dict,
                    sector_data: dict, yesterday_data: dict) -> dict:
    """
    综合评分：基于5维度给出情绪档位（1-5档）
    
    返回结构：
        score: 1-5
        level_name: 恐慌杀跌/偏弱退潮/震荡分化/温和偏多/强主升
        details: 各维度得分
        recommendation: 操作建议
    """
    scores = []
    details = {}

    # ── 维度1：涨停/跌停比 (权重 30%)
    zt = limit_data.get("limit_up_total", 0)
    zd = limit_data.get("limit_down_total", 0)
    if zt > 0 and zd > 0:
        zt_zd_ratio = zt / max(zd, 1)
        if zt_zd_ratio >= 10:
            s1, d1 = 5, "涨停潮"
        elif zt_zd_ratio >= 5:
            s1, d1 = 4, f"多头强({zt}:{zd})"
        elif zt_zd_ratio >= 2:
            s1, d1 = 3, f"偏多({zt}:{zd})"
        elif zt_zd_ratio >= 1:
            s1, d1 = 2, f"偏弱({zt}:{zd})"
        else:
            s1, d1 = 1, f"恐慌({zt}:{zd})"
    elif zt > 0 and zd == 0:
        s1, d1 = 4, "无跌停"
    elif zt == 0 and zd > 0:
        s1, d1 = 1, "无涨停"
    else:
        s1, d1 = 2.5, "数据缺失"
    scores.append(s1 * 0.30)
    details["涨停比"] = d1

    # ── 维度2：涨跌家数比 (权重 25%)
    ratio = ad_data.get("up_ratio", 0.5)
    if ratio >= 0.75:
        s2, d2 = 5, f"偏多({ratio*100:.0f}%上涨)"
    elif ratio >= 0.60:
        s2, d2 = 4, f"温和({ratio*100:.0f}%上涨)"
    elif ratio >= 0.45:
        s2, d2 = 3, f"分化({ratio*100:.0f}%上涨)"
    elif ratio >= 0.30:
        s2, d2 = 2, f"偏弱({ratio*100:.0f}%上涨)"
    else:
        s2, d2 = 1, f"恐慌({ratio*100:.0f}%上涨)"
    scores.append(s2 * 0.25)
    details["涨跌家数"] = d2

    # ── 维度3：北向/港股 (权重 20%)
    hk_chg = nb_data.get("hk_hs", 0)
    if hk_chg <= -2:
        s3, d3 = 1, f"港股大跌({hk_chg:+.2f}%)"
    elif hk_chg <= -1:
        s3, d3 = 2, f"港股小跌({hk_chg:+.2f}%)"
    elif hk_chg <= 0.5:
        s3, d3 = 3, f"港股平({hk_chg:+.2f}%)"
    elif hk_chg <= 1.5:
        s3, d3 = 4, f"港股小涨({hk_chg:+.2f}%)"
    else:
        s3, d3 = 5, f"港股大涨({hk_chg:+.2f}%)"
    scores.append(s3 * 0.20)
    details["港股"] = d3

    # ── 维度4：板块资金 (权重 15%)
    inflow = sector_data.get("top_inflow", [])
    outflow = sector_data.get("top_outflow", [])
    if len(inflow) >= 3 and len(outflow) <= 1:
        s4, d4 = 4, "资金净流入"
    elif len(inflow) >= 1:
        s4, d4 = 3, "部分板块流入"
    elif len(outflow) >= 3:
        s4, d4 = 2, "资金净流出"
    else:
        s4, d4 = 2.5, "数据缺失"
    scores.append(s4 * 0.15)
    details["资金流向"] = d4

    # ── 维度5：昨日涨停今日溢价 (权重 10%)
    avg_gain = yesterday_data.get("avg_gain", 0)
    if not yesterday_data.get("available"):
        s5, d5 = 3, "无数据"
    elif avg_gain >= 5:
        s5, d5 = 5, f"强溢价({avg_gain:+.2f}%)"
    elif avg_gain >= 2:
        s5, d5 = 4, f"正溢价({avg_gain:+.2f}%)"
    elif avg_gain >= 0:
        s5, d5 = 3, f"平溢价({avg_gain:+.2f}%)"
    else:
        s5, d5 = 1, f"炸板({avg_gain:+.2f}%)"
    scores.append(s5 * 0.10)
    details["昨日涨停"] = d5

    # ── 综合评分
    total = sum(scores)
    raw_score = total

    if raw_score >= 4.5:
        level, emoji, rec = "🔥 强主升", 5, "主线明确，满仓不追高"
    elif raw_score >= 3.5:
        level, emoji, rec = "✅ 温和偏多", 4, "热点明确，可尾盘介入"
    elif raw_score >= 2.5:
        level, emoji, rec = "↔️ 震荡分化", 3, "结构行情，精选主线"
    elif raw_score >= 1.5:
        level, emoji, rec = "⚠️ 偏弱退潮", 2, "控仓防守，观望为主"
    else:
        level, emoji, rec = "🔴 恐慌杀跌", 1, "停止选股，空仓风控"

    return {
        "raw_score": round(raw_score, 2),
        "level_id": emoji,
        "level_name": level,
        "recommendation": rec,
        "details": details,
        "weights": {
            "涨停比": "30%",
            "涨跌家数": "25%",
            "港股": "20%",
            "资金流向": "15%",
            "昨日涨停": "10%",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Part 3: 并行扫描
# ─────────────────────────────────────────────────────────────────────────────

def analyze_sentiment() -> dict:
    """
    并行获取所有情绪数据，整合评分。
    与 market_scanner.py 形成互补：
    - market_scanner 取不到的数据（涨跌家数/北向/炸板率），
      sentiment_analyzer 尝试多源备用。
    """
    t0 = time.time()
    results = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "limit_up_down": {},
        "advance_decline": {},
        "northbound": {},
        "sector_flow": {},
        "yesterday_limit": {},
        "us_night": {},
        "sentiment": {},
        "_elapsed": 0,
    }

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(get_limit_up_down): "limit_up_down",
            executor.submit(get_advance_decline_sample): "advance_decline",
            executor.submit(get_northbound_flow): "northbound",
            executor.submit(get_sector_money_flow): "sector_flow",
            executor.submit(get_yesterday_limit_today): "yesterday_limit",
            executor.submit(get_us_night): "us_night",
        }

        for future in as_completed(futures, timeout=TIMEOUT + 2):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"available": False, "error": str(e)[:80]}
                print(f"[sentiment_analyzer] {key} failed: {e}", file=sys.stderr)

    # 综合评分
    results["sentiment"] = score_sentiment(
        results["limit_up_down"],
        results["advance_decline"],
        results["northbound"],
        results["sector_flow"],
        results["yesterday_limit"],
    )

    results["_elapsed"] = round(time.time() - t0, 1)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Part 4: 格式化报告
# ─────────────────────────────────────────────────────────────────────────────

def format_sentiment_report(data: dict, market_scanner_data: dict = None) -> str:
    """
    格式化情绪分析报告（与 market_scanner 报告互补）

    market_scanner_data: 可选，来自 market_scanner.py 的 scan_market() 结果
                        用于交叉验证（指数/板块）
    """
    lines = []
    elapsed = data.get("_elapsed", 0)
    ts = data.get("timestamp", "")

    # ── 标题
    sentiment = data.get("sentiment", {})
    level = sentiment.get("level_name", "未知")
    raw = sentiment.get("raw_score", 0)
    rec = sentiment.get("recommendation", "")

    lines.append(f"🎭 市场情绪分析  {ts}  ⏱{elapsed}s")
    lines.append(f"  情绪档位: {level}  (综合{raw}/5.0)")
    lines.append(f"  建议: {rec}")
    lines.append("")

    # ── 涨停跌停
    limit = data.get("limit_up_down", {})
    if limit.get("available"):
        lines.append("━━ 涨停/跌停 ━━")
        lines.append(
            f"  涨停 {limit.get('limit_up_total', 0)} 家"
            f"  (20%: {limit.get('limit_up_20', 0)} | 10%: {limit.get('limit_up_10', 0)})"
        )
        lines.append(
            f"  跌停 {limit.get('limit_down_total', 0)} 家"
        )
        lines.append("")
    else:
        lines.append("━━ 涨停/跌停 ━━  ❌ 数据不可用")
        lines.append("")

    # ── 涨跌家数
    ad = data.get("advance_decline", {})
    if ad.get("available"):
        lines.append("━━ 涨跌家数（采样估算）━━")
        lines.append(
            f"  上涨 ~{ad.get('up_estimate', 0)} | "
            f"下跌 ~{ad.get('down_estimate', 0)} | "
            f"平 {ad.get('flat_estimate', 0)}"
        )
        lines.append(f"  上涨比: {ad.get('up_ratio', 0)*100:.1f}%")
        note = ad.get("note", "")
        if note:
            lines.append(f"  注: {note}")
        lines.append("")
    else:
        lines.append("━━ 涨跌家数 ━━  ⚠️ 数据不可用（采样估算失败）")
        lines.append("")

    # ── 北向/港股
    nb = data.get("northbound", {})
    lines.append("━━ 港股/北向 ━━")
    hk = nb.get("hk_hs", 0)
    hsce = nb.get("hk_hsce", 0)
    if nb.get("available") and hk != 0:
        arrow = "▲" if hk >= 0 else "▼"
        sign = "+" if hk >= 0 else ""
        lines.append(f"  恒生指数: {arrow}{sign}{hk:.2f}%")
        arrow2 = "▲" if hsce >= 0 else "▼"
        sign2 = "+" if hsce >= 0 else ""
        lines.append(f"  国企指数: {arrow2}{sign2}{hsce:.2f}%")
    else:
        lines.append(f"  恒生指数: ❌ 不可用")
        lines.append(f"  国企指数: ❌ 不可用")
    sh = nb.get("hk_connect_sh")
    sz = nb.get("hk_connect_sz")
    if sh is not None:
        lines.append(f"  沪股通: {'+' if sh >= 0 else ''}{sh}亿")
    if sz is not None:
        lines.append(f"  深股通: {'+' if sz >= 0 else ''}{sz}亿")
    lines.append("")

    # ── 板块资金流向
    sf = data.get("sector_flow", {})
    if sf.get("available"):
        lines.append("━━ 板块资金 Top3 ━━")
        inflow = sf.get("top_inflow", [])
        outflow = sf.get("top_outflow", [])
        if inflow:
            for i, s in enumerate(inflow[:3], 1):
                lines.append(f"  ↑ {i}. {s['name']}  +{s['money']:.1f}亿")
        if outflow:
            for i, s in enumerate(outflow[-3:] if len(outflow) >= 3 else outflow, 1):
                lines.append(f"  ↓ {i}. {s['name']}  {s['money']:.1f}亿")
        if not inflow and not outflow:
            lines.append("  暂无数据")
        lines.append("")
    else:
        lines.append("━━ 板块资金 ━━  ⚠️ 数据不可用")
        lines.append("")

    # ── 昨日涨停今日表现
    yl = data.get("yesterday_limit", {})
    lines.append("━━ 昨日涨停今日 ━━")
    if yl.get("available"):
        total = yl.get("total", 0)
        avg = yl.get("avg_gain", 0)
        bomb = yl.get("bomb_count", 0)
        hold = yl.get("hold_count", 0)
        lines.append(f"  样本: {total}只  平均溢价: {avg:+.2f}%")
        lines.append(f"  继续涨停: {hold}  炸板: {bomb}")
    else:
        note = yl.get("note", "数据源受限")
        lines.append(f"  ❌ {note}")
    lines.append("")

    # ── 美股昨夜
    us = data.get("us_night", {})
    if us.get("available"):
        lines.append("━━ 美股昨夜 ━━")
        us_names = {"dji": "道琼斯", "inx": "标普500", "ndx": "纳指"}
        for key, label in us_names.items():
            d = us.get(key, {})
            if d.get("price", 0) > 0:
                arrow = "▲" if d["chg"] >= 0 else "▼"
                sign = "+" if d["chg"] >= 0 else ""
                lines.append(
                    f"  {label}  {d['price']:,.0f}  {arrow}{sign}{d['chg_pct']:.2f}%"
                )
    else:
        lines.append("━━ 美股昨夜 ━━  ❌ 不可用")
    lines.append("")

    # ── 情绪评分明细
    if sentiment.get("details"):
        lines.append("━━ 情绪评分明细 ━━")
        details = sentiment["details"]
        weights = sentiment.get("weights", {})
        for dim, desc in details.items():
            w = weights.get(dim, "")
            lines.append(f"  {dim:12s} {desc}  ({w})")
        lines.append("")

    # ── 交叉验证（market_scanner 数据）
    if market_scanner_data:
        lines.append("━━ 交叉验证（market_scanner）━━")
        idx = market_scanner_data.get("index", {})
        for key, label in [("sh", "上证"), ("sz", "深证"), ("cyb", "创业板")]:
            d = idx.get(key, {})
            if d:
                arrow = "▲" if d.get("change", 0) >= 0 else "▼"
                sign = "+" if d.get("change", 0) >= 0 else ""
                pct = d.get("change_pct", 0)
                lines.append(
                    f"  {label}  {d.get('price', 0):,.0f}  {arrow}{sign}{pct:.2f}%"
                )
        sc = market_scanner_data.get("sectors", [])
        if sc:
            lines.append(f"  热门: {', '.join(s.get('name','') for s in sc[:3])}")
    else:
        lines.append("━━ 交叉验证 ━━  （未提供 market_scanner 数据）")

    return "\n".join(lines)


def get_brief_summary(data: dict) -> str:
    """
    简短版情绪摘要，用于快速判断
    """
    sentiment = data.get("sentiment", {})
    level = sentiment.get("level_name", "未知")
    rec = sentiment.get("recommendation", "")
    limit = data.get("limit_up_down", {})
    ad = data.get("advance_decline", {})

    zt = limit.get("limit_up_total", "?")
    zd = limit.get("limit_down_total", "?")
    ratio = ad.get("up_ratio", 0) * 100

    return (
        f"{level} | 涨停{zt}:跌停{zd} | 上涨比{ratio:.0f}% | "
        f"建议: {rec}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from market_scanner import scan_market, format_market_report

    print("=" * 50)
    print("正在并行扫描市场数据 + 情绪分析...")
    print("=" * 50)

    # 先尝试 market_scanner
    mkt = scan_market()
    print("\n【market_scanner 结果】")
    print(format_market_report(mkt))

    # 再运行 sentiment_analyzer
    sent = analyze_sentiment()
    print("\n【sentiment_analyzer 结果】")
    print(format_sentiment_report(sent, market_scanner_data=mkt))

    print("\n【简短摘要】")
    print(get_brief_summary(sent))

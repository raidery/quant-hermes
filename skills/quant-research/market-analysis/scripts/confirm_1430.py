"""
14:30 二次确认脚本
读取当日选股数据 → 腾讯批量查实时价 → 过滤 → 计算买卖价 → 保存

Usage:
    python3 confirm_1430.py
"""

import sys, os, json, time
from datetime import datetime

from pathlib import Path

SCRIPT_DIR    = Path(__file__).parent.resolve()
SKILL_DIR     = SCRIPT_DIR.parent                    # market-analysis/
SELECTION_DIR = SKILL_DIR / "memory" / "selections"
OUT_FILE  = f"/tmp/aftermarket_{datetime.now().strftime('%Y-%m-%d')}.txt"

# 路径：finance-news 的 market_quotes（腾讯行情）
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "finance-news" / "scripts"))
from market_quotes import TencentMarket


def load_today_selections() -> dict | None:
    """读取今日选股数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    sel_file = SELECTION_DIR / f"{today}.json"
    if not sel_file.exists():
        print(f"ERROR: 选股数据不存在 {sel_file}", file=sys.stderr)
        return None
    with open(sel_file) as f:
        return json.load(f)


def build_price_map(candidates: list[dict]) -> dict[str, dict]:
    """腾讯批量查询实时价格，返回 {code: {price, chg, turnover}}"""
    # 转换代码：6开头→sh，0/3开头→sz
    formatted = []
    code_map = {}
    for c in candidates:
        code = c["code"]
        if code.startswith("6"):
            api_code = f"sh{code}"
        elif code.startswith(("0", "3")):
            api_code = f"sz{code}"
        elif code.startswith("8") or code.startswith("4"):
            api_code = f"bj{code}"   # 北交所
        else:
            api_code = code
        formatted.append(api_code)
        code_map[api_code] = code

    if not formatted:
        return {}

    quotes = TencentMarket.fetch_all(codes=formatted)
    price_map = {}
    for q in quotes:
        canon = code_map.get(q.symbol, q.symbol)
        price_map[canon] = {
            "price": q.price,
            "chg": q.change_pct,
            "volume": q.volume,
            "turnover": q.turnover,
        }
    return price_map


def apply_filter(candidates: list[dict], price_map: dict[str, dict]) -> list[dict]:
    """
    14:30 过滤规则：
    - 涨幅 ≤ 6%（追高风险）
    - 涨幅 ≥ -3%（跌幅超-3%则止损条件已触发，放弃）
    - 换手率 ≤ 15%（过度炒作风险）
    同时计算：买入价 = 当前价×0.99，止损价 = 买入价×0.97
    """
    after = []
    for c in candidates:
        code = c["code"]
        pdata = price_map.get(code, {})
        price  = pdata.get("price", c.get("price", 0))
        chg    = pdata.get("chg", c.get("chg", 0))
        turn   = pdata.get("turnover", c.get("turnover", 0))

        c["price_1430"] = price
        c["chg"] = chg
        c["turnover"] = turn

        if chg > 6.0:
            c["filter_reason"] = "涨幅>6%放弃"
            continue
        if chg < -3.0:
            c["filter_reason"] = "跌幅>-3%已触发止损条件"
            continue
        if turn > 15.0:
            c["filter_reason"] = "换手率>15%排除"
            continue

        buy_price  = round(price * 0.99, 2)
        stop_price = round(buy_price * 0.97, 2)
        c["buy_price"]  = buy_price
        c["stop_price"] = stop_price
        c["filter_reason"] = "通过"
        after.append(c)

    return after


def save_filtered(data: dict, after_filter: list[dict]) -> str:
    """更新并保存选股数据（加入 after_14_30_filter 和 final_recommendations）"""
    today = datetime.now().strftime("%Y-%m-%d")
    sel_file = SELECTION_DIR / f"{today}.json"

    # 更新策略结果中的 after_14_30_filter
    strategy_results = data.get("strategy_results", {})
    for sid, sdata in strategy_results.items():
        sdata["after_14_30_filter"] = [
            {k: v for k, v in c.items()
             if k in ["code", "name", "chg", "turnover", "price_1430", "buy_price", "stop_price"]}
            for c in after_filter
            if c.get("strategy") == sdata.get("query")
        ]

    data["final_recommendations"] = after_filter
    data["filter_applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(sel_file, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(sel_file)


def format_report(data: dict, after_filter: list[dict], before_count: int) -> str:
    """格式化 14:30 二次确认报告（emoji 纯文本）"""
    today = datetime.now().strftime("%Y-%m-%d")
    selected = data.get("selected_strategies", [])

    lines = [
        f"⏰ 14:30 二次确认报告",
        f"  日期: {today}",
        f"  策略: {', '.join(selected)}",
        "",
        f"  候选总数: {before_count} 只",
        f"  14:30过滤后: {len(after_filter)} 只",
        f"  淘汰: {before_count - len(after_filter)} 只",
        "",
    ]

    if not after_filter:
        lines.append("  ⚠️ 无通过标的，建议空仓观望")
        return "\n".join(lines)

    lines.append("━ 二次确认标的 ━━")
    lines.append(f"  {'代码':<10} {'名称':<8} {'现价':>7} {'涨幅':>7} {'换手率':>7}  {'买入价':>7} {'止损价':>7}  {'状态'}")
    lines.append("─" * 80)

    for c in sorted(after_filter, key=lambda x: -x.get("chg", 0)):
        arrow = "▲" if c.get("chg", 0) >= 0 else "▼"
        sign  = "+" if c.get("chg", 0) >= 0 else ""
        turn  = c.get("turnover", 0)
        turn_str = f"{turn:.1f}%" if turn else "N/A"
        lines.append(
            f"  {c['code']:<10} {c.get('name',''):<8} "
            f"{c.get('price_1430', 0):>7.2f} "
            f"{arrow}{sign}{c.get('chg', 0):>6.2f}% "
            f"{turn_str:>7} "
            f"{c.get('buy_price', 0):>7.2f} "
            f"{c.get('stop_price', 0):>7.2f}  "
            f"✅通过"
        )

    lines.append("")
    lines.append("━ 买卖计划 ━━")
    for c in sorted(after_filter, key=lambda x: -x.get("chg", 0)):
        lines.append(
            f"  {c.get('name', c['code'])} ({c['code']})\n"
            f"    买入价: {c.get('buy_price', 0):.2f}（现价×0.99）\n"
            f"    止损价: {c.get('stop_price', 0):.2f}（买入价×0.97，跌幅-3%）"
        )
        reason = c.get("strategy", "")
        if reason:
            lines.append(f"    来源: {reason}")
        lines.append("")

    lines.append("⚠️ 仅供参考，不构成投资建议")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")

    # Step 1: 读取选股数据
    data = load_today_selections()
    if not data:
        sys.exit(1)

    candidates = data.get("candidates", [])
    before_count = len(candidates)
    print(f"[14:30] 读取候选 {before_count} 只")

    if before_count == 0:
        print("ERROR: 无候选数据，请检查选股初筛cron是否正常执行")
        sys.exit(1)

    # Step 2: 批量查询实时价格
    print(f"[14:30] 查询实时价格...")
    price_map = build_price_map(candidates)
    print(f"[14:30] 获取到 {len(price_map)} 只价格数据")

    # Step 3: 过滤
    after_filter = apply_filter(candidates, price_map)
    print(f"[14:30] 过滤后: {len(after_filter)} 只 (淘汰 {before_count - len(after_filter)} 只)")

    # Step 4: 保存
    saved_path = save_filtered(data, after_filter)
    print(f"[14:30] 数据已更新: {saved_path}")

    # Step 5: 写临时输出文件（供 cron prompt 读取）
    lines = [
        f"DATE:{today}",
        f"AFTER_FILTER_COUNT:{len(after_filter)}",
        f"BEFORE_COUNT:{before_count}",
        f"SAVED:{saved_path}",
        "RECOMMENDATIONS:"
    ]
    for c in sorted(after_filter, key=lambda x: -x.get("chg", 0)):
        lines.append(
            f"{c.get('code','')}|{c.get('name','')}|{c.get('price_1430', 0):.2f}|"
            f"{c.get('chg', 0):.2f}%|{c.get('turnover', 0):.2f}%|"
            f"{c.get('strategy','')}|买入:{c.get('buy_price', 0):.2f}|止损:{c.get('stop_price', 0):.2f}"
        )
    with open(OUT_FILE, "w") as f:
        f.write("\n".join(lines))
    print(f"[14:30] 临时文件已写入: {OUT_FILE}")

    # Step 6: 打印报告
    report = format_report(data, after_filter, before_count)
    print("\n" + "=" * 55)
    print(report)

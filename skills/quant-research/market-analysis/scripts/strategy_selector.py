"""
市场自适应选股核心模块 - Hermes 版本
封装选股查询逻辑，供 cron 和交互式调用共用

依赖：
  - quant-claw-skill/query.py（问财）
  - quant-research/finance-news/scripts/market_quotes.py（腾讯行情）

⚠️ 策略模板统一从以下 JSON 加载，禁止维护硬编码副本：
  ~/.hermes/skills/quant-research/strategy-templates/strategy-templates.json
"""

import sys, os, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 路径
SKILL_DIR = Path(__file__).parent.parent.parent.resolve()   # quant-research/
WENCAI_DIR = "/home/claw/.hermes/skills/quant-claw-skill"
MEMORY_DIR = Path(__file__).parent.parent / "memory"       # market-analysis/memory/
MEMORY_DIR.mkdir(exist_ok=True)

sys.path.insert(0, WENCAI_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# 策略模板加载（直接读 JSON，禁止维护硬编码副本）
# 数据源：~/.hermes/skills/quant-research/strategy-templates/strategy-templates.json
# ─────────────────────────────────────────────────────────────────────────────

_TPL_PATH = Path.home() / ".hermes/skills/quant-research/strategy-templates/strategy-templates.json"

def _load_templates():
    with open(_TPL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("strategies", [])

_STRATEGIES = None   # 懒加载缓存

def _get_strategies():
    global _STRATEGIES
    if _STRATEGIES is None:
        _STRATEGIES = {s["id"]: s for s in _load_templates()}
    return _STRATEGIES

def list_active_ids() -> list[str]:
    """返回当前激活的策略 ID 列表"""
    tpl_path = Path.home() / ".hermes/skills/quant-research/strategy-templates/strategy-templates.json"
    with open(tpl_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("active", [])

def get_template_by_id(strategy_id: str) -> dict:
    """返回完整策略模板 dict，KeyError 如果不存在"""
    strategies = _get_strategies()
    if strategy_id not in strategies:
        raise KeyError(f"未找到策略: {strategy_id}")
    return strategies[strategy_id]

def get_wencai_query(strategy_id: str) -> str:
    """返回策略的 wencai_query 字符串"""
    tpl = get_template_by_id(strategy_id)
    query = tpl.get("wencai_query", "")
    if not query:
        raise ValueError(f"策略 {strategy_id} 没有 wencai_query 字段")
    return query


# ─────────────────────────────────────────────────────────────────────────────
# 问财查询
# ─────────────────────────────────────────────────────────────────────────────

def wencai_query(query: str, max_count: int = 20) -> list[dict]:
    """
    通过 quant-claw-skill 执行问财查询。
    Returns list of dict with keys: code, name, chg, price, ...
    """
    cookie_path = os.path.join(WENCAI_DIR, ".wencai_cookie")
    if not os.path.exists(cookie_path):
        print(f"[strategy_selector] WARN: cookie not found at {cookie_path}", file=sys.stderr)
        return []

    env = os.environ.copy()
    env["WENCAI_COOKIE"] = open(cookie_path).read().strip()

    import subprocess
    python = "/home/claw/.hermes/hermes-agent/venv/bin/python3"

    try:
        result = subprocess.run(
            [python, "query.py", query, "--max", str(max_count)],
            cwd=WENCAI_DIR,
            capture_output=True, text=True, timeout=120, env=env
        )
        if result.returncode != 0:
            print(f"[strategy_selector] query failed: {result.stderr[:200]}", file=sys.stderr)
            return []

        # 解析 CSV 输出:
        # | 000762.SZ  | 西藏矿业   |    33.88 |      10      |            33 | 000762 |
        # [0]         [1]          [2]         [3]            [4]            [5]
        # parts[1]=code, parts[2]=name, parts[3]=price, parts[4]=chg_pct
        candidates = []
        for line in result.stdout.strip().split("\n"):
            stripped = line.strip()
            if "|" not in stripped or "代码" in stripped or "股票代码" in stripped:
                continue
            if ":" in stripped or "---" in stripped or stripped.startswith("+"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            try:
                code = parts[1].strip()
                name = parts[2].strip()
                price_str = parts[3].strip().replace(",", "")
                chg_str = parts[4].strip().replace("%", "").replace("+", "").replace("=", "")
                price = float(price_str) if price_str else 0.0
                chg = float(chg_str) if chg_str else 0.0
                if price < 1:
                    continue
                candidates.append({
                    "code": code,
                    "name": name,
                    "price": price,
                    "chg": chg,
                    "strategy": query,
                })
            except (ValueError, IndexError):
                continue
        return candidates

    except Exception as e:
        print(f"[strategy_selector] exception: {e}", file=sys.stderr)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 核心函数
# ─────────────────────────────────────────────────────────────────────────────

def run_selected_strategies(
    selected_strategy_ids: list[str],
    held: set[str] = None,
    max_per_strategy: int = 20
) -> tuple[dict, list[dict]]:
    """
    执行选中的策略，返回 (strategy_results, all_candidates)

    Args:
        selected_strategy_ids: 策略ID列表，如 ["隔夜持股v2.2", "资金共振选股v2.1"]
        held: 需要排除的持仓代码集合
        max_per_strategy: 每个策略最多返回数量
    Returns:
        (strategy_results dict, all_candidates list)
    """
    if held is None:
        held = set()

    strategy_results = {}
    all_candidates = []

    for sid in selected_strategy_ids:
        try:
            tpl = get_template_by_id(sid)
        except (KeyError, ValueError) as e:
            print(f"[strategy_selector] WARN: {e}", file=sys.stderr)
            continue

        try:
            query = get_wencai_query(sid)
        except ValueError:
            print(f"[strategy_selector] WARN: strategy {sid} has no wencai_query", file=sys.stderr)
            continue
        results = wencai_query(query, max_count=max_per_strategy)

        # 过滤排除持仓
        filtered = [r for r in results if r["code"] not in held]

        strategy_results[sid] = {
            "query": query,
            "total": len(results),
            "filtered": len(filtered),
            "candidates": filtered[:max_per_strategy],
        }
        all_candidates.extend(filtered[:max_per_strategy])

    return strategy_results, all_candidates


def save_selection_data(
    selected: list[str],
    strategy_results: dict,
    all_candidates: list[dict]
) -> str:
    """
    保存选股数据到 memory/ 目录。
    Returns: 保存的文件路径
    """
    today = time.strftime("%Y-%m-%d")
    out_dir = MEMORY_DIR / "selections"
    out_dir.mkdir(exist_ok=True)

    filepath = out_dir / f"{today}.json"
    payload = {
        "date": today,
        "selected_strategies": selected,
        "strategy_results": strategy_results,
        "candidates": all_candidates,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(filepath, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return str(filepath)


def format_selection_report(strategy_results: dict, all_candidates: list[dict]) -> str:
    """格式化选股报告（emoji 纯文本）"""
    共振 = [c for c in all_candidates if "+" in c.get("strategy", "")]
    单独 = [c for c in all_candidates if "+" not in c.get("strategy", "")]
    filtered_6pct = [c for c in all_candidates if c["chg"] <= 6.0]

    lines = [
        f"📋 选股初筛报告",
        f"  策略数: {len(strategy_results)} | 总候选: {len(all_candidates)} 只",
        f"  共振: {len(共振)} 只 | 涨幅≤6%: {len(filtered_6pct)} 只",
        "",
    ]

    if 共振:
        lines.append("━ 共振标的 ━")
        for c in 共振[:10]:
            arrow = "▲" if c["chg"] >= 0 else "▼"
            sign = "+" if c["chg"] >= 0 else ""
            lines.append(
                f"  {c['code']} {c['name']:<10} {arrow} {sign}{c['chg']:>6.2f}%  {c.get('strategy','')}"
            )

    if 单独:
        lines.append("")
        lines.append("━ 单独策略 Top10 ━")
        for c in 单独[:10]:
            arrow = "▲" if c["chg"] >= 0 else "▼"
            sign = "+" if c["chg"] >= 0 else ""
            lines.append(
                f"  {c['code']} {c['name']:<10} {arrow} {sign}{c['chg']:>6.2f}%"
            )

    lines.append("")
    lines.append("  ⚠️ 仅供参考，不构成投资建议")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="市场自适应选股")
    parser.add_argument("--strategies", nargs="+",
                        default=["隔夜持股v2.2", "趋势回踩确认v1.0"],
                        help="策略ID列表")
    parser.add_argument("--held", nargs="*", default=[], help="排除的持仓代码")
    args = parser.parse_args()

    held = set(args.held)
    results, candidates = run_selected_strategies(args.strategies, held=held)
    filepath = save_selection_data(args.strategies, results, candidates)
    report = format_selection_report(results, candidates)
    print(report)
    print(f"\n✅ 数据已保存: {filepath}")

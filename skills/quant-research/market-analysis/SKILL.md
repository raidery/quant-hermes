---
name: market-analysis
description: 市场自适应选股 — 大盘扫描 + 情绪分析 + CoT推理 + 策略选择 + 问财共振
category: quant-research
tags: [选股, 大盘扫描, 情绪分析, 量化]
version: 1.3.0
---

# 市场自适应选股

盘中 13:00 执行：**大盘扫描 → 情绪评分 → CoT策略选择 → 问财共振 → 14:30二次确认**

---

## 核心模块

```
scripts/market_scanner.py      — 指数/板块/美股（腾讯+东方财富）
scripts/sentiment_analyzer.py  — 情绪/涨跌家数/涨停/北向（互补）
scripts/strategy_selector.py   — 策略选择 + 问财查询
scripts/confirm_1430.py       — 14:30 二次确认
```

---

## 情绪档位（前置，必须先判断）

| 档位 | 市场 | 操作 |
|------|------|------|
| 🔴 恐慌杀跌 | 跌多涨少 | 停止选股，空仓 |
| ⚠️ 偏弱退潮 | 涨少跌多 | 控仓观望 |
| ↔️ 震荡分化 | 结构行情 | 精选主线，不追高 |
| ✅ 温和偏多 | 热点明确 | 可尾盘介入 |
| 🔥 强主升 | 涨停潮 | 主线满仓，止损放-5% |

---

## 工作流程

```
1. scan_market() + analyze_sentiment()  并行执行
2. 情绪档位判断  →  恐慌/退潮则停
3. LLM根据市场数据+情绪档位  选择2-3个策略
4. 执行问财查询  →  多策略共振标的优先
5. 排除：涨幅>6%、跌幅>-3%、换手>15%
6. 排除：涨停潮板块内的标的（板块批量涨停=排除信号）
7. 保存 selections/{date}.json
8. 14:30 confirm_1430.py 二次确认
```

---

## 14:30 过滤规则

- 买入价 = 现价 × 0.99
- 止损价 = 买入价 × 0.97（≈跌3%）
- 涨幅 ≤ 6%、跌幅 ≥ -3%、换手率 ≤ 15%

## 涨停潮板块排除规则（铁律）

当某板块出现**批量涨停潮**（如锂电/稀有金属等）时：
- 板块内**所有标的**一律从候选中排除，不追涨停
- 高开 > 6% 的标的立即标记"放弃"，不等 14:30
- 低开 < 0% 但有主力流入的标的，可作为反向买点候选
- 原因：涨停潮板块追买胜率极低，次日溢价有限

---

## 铁律

1. 止损 -3% 无条件执行
2. 涨幅 > 3% 不买（禁止高开追）
3. 持仓 ≤ 3 只，单票 ≤ 30%
4. 最佳买入：尾盘 14:30 后
5. 恐慌/偏弱 → 直接空仓，不选股
6. **涨停潮板块整体排除** — 批量涨停板块不追买

---

## 策略模板（适合市场/仓位）

| 策略 | 适合 | 仓位 |
|------|------|------|
| 隔夜持股v2.2 | 强势 | 30% |
| 趋势回踩确认v1.0 | 趋势 | 30% |
| 资金共振选股v2.1 | 通用 | 30% |
| 突破新高确认v2.0 | 强势 | 20% |
| 首板战法v1.0 | 强势 | 20% |

---

## 数据源

| 数据 | 来源 | 限制 |
|------|------|------|
| A股指数 | 腾讯 qt.gtimg.cn | 稳定 |
| 港股/恒生 | 腾讯 s_hkHSI/s_hkHSCEI | 字段[5]=涨跌幅% |
| 涨跌家数 | 新浪双采样 | 估算，非精确 |
| 涨停/跌停 | 东方财富 push2 | 盘中可能断 |
| 北向资金 | 腾讯港股（间接） | 无直接接口 |
| 昨日涨停今日 | 新浪 hs_zte | 不稳定 |
| 美股 | 腾讯 usNDX/usINX | 盘后 |

---

## 触发词

```
选股初筛 / 今日选股 / 情绪分析 / 今日情绪 / 大盘扫描 / 今日主线
```

## 用法

```python
from market_analysis.scripts.market_scanner import scan_market
from market_analysis.scripts.sentiment_analyzer import analyze_sentiment, get_brief_summary

mkt = scan_market()
sent = analyze_sentiment()
print(get_brief_summary(sent))  # 简短摘要
```

## ⚠️ 已知坑（2026-04-14）

### 1. ✅ 已修复 P0：`strategy_selector.py` 导入路径错误

`strategy_selector.py`、`workflow.py`、`second_confirm.py` 三个文件之前导入了不存在的 `tools._strategy_loader`。
**已在 v1.2.1 修复**：策略模板改为直接读取 `strategy-templates.json`，不再依赖 `_strategy_loader`。

### 2. JSON 结构（v12）
```python
# 正确读取方式
with open('/home/claw/.hermes/skills/quant-research/strategy-templates/strategy-templates.json') as f:
    data = json.load(f)
active_ids = data['active']               # list: ["隔夜持股v2.2", ...]
strategies_map = {s['id']: s for s in data['strategies']}  # dict
```

### 3. 🔴 P1 待修复：硬性暂停条件没有代码实现

AGENTS.md 定义了硬性暂停条件：
- 上证 < -1.5% → 停止所有买入
- 下跌家数 > 上涨家数 × 2 → 停止所有买入

**现状**：`sentiment_analyzer.py` 和 `market_scanner.py` 中**没有任何代码**判断这两个条件。
需要在此流程的前置阶段补充实现。

### 4. 🟡 P1 待修复：北向资金数据几乎全为空

`sentiment_analyzer.get_northbound_flow()` 只能获取恒生指数涨跌幅，
沪股通/深股通净流入、北向合计净流入**全为 None**。
建议接入东方财富沪深港通接口。

### 5. 🟡 P1 待修复：涨跌家数估算精度问题

新浪双采样方法固定假设 A 股总数 5300，采样量不对称（涨3000/跌1000）。
建议改用东方财富 ulist 接口获取精确涨跌家数。

`sentiment_analyzer.py` 的 `get_northbound_flow()` 只查了港股指数（恒生/国企）作为代理变量，
真正的沪股通/深股通净流入**全是 None**。评分权重 20% 的"港股/北向"维度实际上只有港股指数涨跌幅一个数字。

### 5. 14:30 过滤混用两个数据源

`confirm_1430.py` 的 `apply_filter()`：
```python
chg = pdata.get("chg_pct", c.get("chg_pct", 0))  # 腾讯实时涨幅 OR 问财原始涨幅
```
问财涨幅是静态收盘数据，腾讯涨幅是实时数据，两个口径不同。过滤应**只用问财原始涨幅**，实时价格只用来计算买卖价。

### 6. 数据重复：`market_scanner` 和 `sentiment_analyzer` 都查涨停

两者都从东方财富 `push2.eastmoney.com` 查涨停/跌停，但解析逻辑不同，结果可能矛盾。
`market_scanner.get_limit_up_count()` 只返回 `{"limit_up": N}`（没有跌停），
`sentiment_analyzer.get_limit_up_down()` 两者都有。建议统一到 `sentiment_analyzer`，`market_scanner` 引用其结果。

### 7. "半手动"模式的真实含义

**不是"系统自动委托"，而是"系统生成候选 → 写临时文件 → 等用户主动来查"**：
- Cron 13:00 → 保存 `selections/{date}.json`
- Cron 14:30 → 读取 JSON → 过滤 → 输出 `/tmp/aftermarket_{date}.txt`
- **没有自动推送机制**，用户必须问"今日选股"才能看到结果

如需自动推送，需在 `confirm_1430.py` 的 `__main__` 末尾接入 `send_message` 或 cron deliver。

### 8. 持仓超限不阻止

铁律"持仓 ≤ 3 只"只有 `print()` 提示，**没有任何机制阻止超限买入**。建议在 `confirm_1430.py` 输出中加入持仓数量检查。

### 9. 过滤结果没有选股评分

SKILL.md 说"评分≥75优先，<60排除"，但 `apply_filter()` 没有调用评分模块，排序只用涨幅。评分模块 (`score_calibration.py`) 需要接入此流程。

## 持仓路径

`~/.hermes/skills/quant-strategy/memory/holdings.json`

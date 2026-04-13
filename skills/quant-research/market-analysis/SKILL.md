---
name: market-analysis
description: 市场自适应选股 — 大盘扫描 + 情绪分析 + CoT推理 + 策略选择 + 问财共振
category: quant-research
tags: [选股, 大盘扫描, 情绪分析, 量化]
version: 1.1.0
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
6. 保存 selections/{date}.json
7. 14:30 confirm_1430.py 二次确认
```

---

## 14:30 过滤规则

- 买入价 = 现价 × 0.99
- 止损价 = 买入价 × 0.97（≈跌3%）
- 涨幅 ≤ 6%、跌幅 ≥ -3%、换手率 ≤ 15%

---

## 铁律

1. 止损 -3% 无条件执行
2. 涨幅 > 3% 不买（禁止高开追）
3. 持仓 ≤ 3 只，单票 ≤ 30%
4. 最佳买入：尾盘 14:30 后
5. 恐慌/偏弱 → 直接空仓，不选股

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

## 持仓路径

`~/.hermes/skills/quant-strategy/memory/holdings.json`

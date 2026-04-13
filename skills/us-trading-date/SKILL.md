---
name: us-trading-date
description: "从中国金融API的HTTP响应头中自动计算美股交易日。用于腾讯财经美股行情等中国接口获取不包含日期字段的数据时，确定其对应的美股交易日期。"
version: 1.0
author: Hermes Agent
category: quant-research
---

# US Trading Date Determination

## Problem

中国金融API（如腾讯财经 qt.gtimg.cn）返回的美股行情数据本身不包含日期字段，只有价格/涨跌幅。需要根据请求时间推算数据对应的美股交易日。

## Algorithm

```
输入：HTTP响应头的 Date 字段（GMT格式，如 "Sun, 12 Apr 2026 19:53:45 GMT"）

Step 1: GMT → 北京时间（UTC+8）
Step 2: 北京时间 04:00 为美股交易日分界
         · 04:00-23:59 → 当天即为美股交易日
         · 00:00-03:59 → 上一个美股交易日（往前减1天）
Step 3: 如果计算出的是周六/周日 → 继续往前回退到最近的周五
输出：YYYY-MM-DD 格式的美股交易日
```

## 关键边界条件

| 北京时间 | 美股交易日 |
|---------|-----------|
| 周一 04:00-23:59 | 当天周一 |
| 周二-周五 04:00-23:59 | 当天 |
| 周六 00:00-03:59 | 上周五（先减1天=周五，但4点前是周四？→ 实际回退到上周五）|
| 周六 04:00-23:59 | 上周五（减1天=周五，停止） |
| 周日 00:00-03:59 | 上周五（减1天=周六，回退到周五） |
| 周日 04:00-23:59 | 上周五（当天=周日，回退到周五） |

## Python 实现

```python
from datetime import datetime, timezone, timedelta

gmt_str = response.headers.get("Date", "")
gmt_dt = datetime.strptime(gmt_str, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
beijing_dt = gmt_dt.astimezone(timezone(timedelta(hours=8)))

us_day = beijing_dt.date()
if beijing_dt.hour < 4:
    us_day = (beijing_dt - timedelta(days=1)).date()

# Roll back Sat/Sun to preceding Fri
while us_day.isoweekday() >= 6:  # 6=Sat, 7=Sun
    us_day -= timedelta(days=1)

trading_date = us_day.strftime("%Y-%m-%d")  # e.g. "2026-04-10"
```

## 应用场景

- 腾讯财经美股行情（qt.gtimg.cn）— 字段 [3]=价格 [4]=涨跌 [5]=涨跌幅，无日期
- 其他中国金融接口返回实时数据但不附日期时适用

## 验证

- 周日北京时间 03:53 → GMT 前一天 19:53 → 计算出周六 → 回退到上周五
- 周五北京时间 20:00 → 当天周五，直接使用
- 周六北京时间 12:00 → 当天周六 → 回退到上周五

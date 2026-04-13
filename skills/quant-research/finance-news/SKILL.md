---
name: finance-news
description: "抓取东方财富、同花顺、新浪财经、财联社实时财经快讯 + 腾讯财经全球市场行情（A股/港股/美股）。全部直接HTTP，不依赖Browser Use。"
version: 1.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [finance, news, scraper, eastmoney, iwencai, sina, cailian, tencent, us-stock, china, stock, futures, hk-stock, global-market]
    category: research
    trigger: "财经|新闻|快讯|A股|期货|宏观|选股|股市|美股|夜盘|道琼斯|标普|纳斯达克|VIX|全球市场|恒生|上证|深证|创业板"
required_packages: [httpx, requests]
hermes:
  cron:
    # deliver 必须用 "feishu"，不能用 "origin"！
    # cron session 无活跃聊天上下文，origin 找不到投递目标
    # 必须配合 FEISHU_HOME_CHANNEL 环境变量
    deliver_note: "deliver=feishu（不要用 origin）"
---

# Finance News Scraper

## 功能

统一抓取国内财经快讯 + 美股夜盘，**全部直接 HTTP，不依赖 Browser Use**：

| 来源 | 简称 | 支持分类 | 状态 |
|------|------|---------|------|
| 东方财富 | eastmoney | A股/期货/宏观/港股/美股/综合 | ✅ 直接API |
| 同花顺 | iwencai | 智能选股/期货 | ✅ 代理东方财富API |
| 新浪财经 | sina | 全球宏观/财经快讯 | ✅ 直接API |
| 财联社 | cailian | A股/期货/宏观/港美股/公司等全分类 | ✅ HTML解析（requests+BeautifulSoup） |
| 腾讯财经 | tencent | 道琼斯/标普500/纳斯达克100/VIX恐慌指数 | ✅ 直接API（国内直连） |

## API（2026-04-12 确认）

**东方财富快讯**（稳定，无需认证）:
```
https://newsapi.eastmoney.com/kuaixun/v1/getlist_{channel}_ajaxResult_{pageSize}_{pageNum}_.html
Channel IDs: 101=综合, 102=A股, 105=港股, 106=美股, 107=期货, 109=宏观
响应格式: var ajaxResult={...JSON...}
```

**新浪财经**（稳定，无需认证）:
```
https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num={n}&page=1
lid=2516 = 实时股票/全球宏观快讯
```

**财联社**（稳定，无需认证）：
```
https://www.cls.cn/telegraph
数据位置: HTML内联JSON，window.__NEXT_DATA__["props"]["initialState"]["telegraph"]["telegraphList"]
解析方式: requests + BeautifulSoup，从原始HTML提取内联JSON
```

**腾讯财经美股指数**（稳定，国内直连，无需认证）:
```
https://qt.gtimg.cn/q=s_usDJI,s_usINX,s_usNDX,s_usVIX
编码: GBK
返回格式: v_s_usDJI="股票名~...~代码~现价~涨跌额~涨跌幅~..."
关键字段: [3]=现价 [4]=涨跌额 [5]=涨跌幅(%)
```

## 使用方式

```python
import sys
sys.path.insert(0, "/home/claw/.hermes/skills/quant-research/finance-news/scripts")
from scraper import FinanceNewsScraper, TencentUSMarket

scraper = FinanceNewsScraper()

# ── 快讯（按分类）──
items = scraper.fetch_by_category("A股")     # → 东方财富
items = scraper.fetch_by_category("期货")    # → 东方财富
items = scraper.fetch_by_category("宏观")    # → 新浪财经

# ── 多源合并抓取──
items = scraper.fetch_all(sources=["eastmoney", "sina", "iwencai", "cailian"])

# ── 美股夜盘（腾讯财经，国内直连）──
from market_quotes import TencentMarket, format_global_report
print(TencentMarket.format_global_report())    # 全球市场（A 股+港股+美股）
print(TencentMarket.format_global_report(markets=["美股"]))  # 仅美股

# ── 输出Markdown──
print(scraper.to_markdown(items))
```

**触发词**（直接说话即可）：
```
"美股夜盘" / "道琼斯" / "标普500" / "纳斯达克" / "VIX"
"今日美股行情" / "美股收盘"
```

## 文件结构

```
finance-news/
├── SKILL.md          ← 你在这里
└── scripts/
    ├── __init__.py
    └── scraper.py    ← 核心实现
```

## 定时任务示例

```bash
hermes cron create \
  --name "A股快讯" \
  --prompt "抓取A股快讯，输出markdown格式，保存到 ~/.hermes/finance-news/output/daily.md" \
  --schedule "*/30 * * * *" \
  --deliver local
```

## 依赖

- `httpx`（已安装）

## 已知限制

- 华尔街见闻无公开可用API，已用新浪财经 lid=2516 替代
- 同花顺无独立公开API，代理东方财富数据

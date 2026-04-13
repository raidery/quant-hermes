# finance-news 使用参考

## 快速使用

```python
import sys
sys.path.insert(0, '/home/claw/.hermes/skills/quant-research/finance-news/scripts')
from scraper import FinanceNewsScraper
import logging
logging.basicConfig(level=logging.WARNING)

scraper = FinanceNewsScraper()

# 按分类抓取（自动选来源）
items = scraper.fetch_by_category("A股")    # → 东方财富
items = scraper.fetch_by_category("期货")    # → 东方财富
items = scraper.fetch_by_category("宏观")    # → 新浪财经

# 多源合并（4个来源）
items = scraper.fetch_all(sources=['eastmoney', 'sina', 'iwencai', 'cailian'], page_size=20)

# 单源测试
items = scraper.fetch('cailian', 'fetch_latest', limit=10).items

# 输出 Markdown
print(scraper.to_markdown(items))
```

## 全球市场行情（腾讯财经）

```python
from market_quotes import TencentMarket, format_global_report

# 全球市场总览（A 股+港股+美股，一次请求）
print(TencentMarket.format_global_report())

# 仅美股夜盘
print(TencentMarket.format_global_report(markets=["美股"]))

# 指定市场
print(TencentMarket.format_global_report(markets=["A股", "港股"]))
```

**触发词**：
```
"全球市场" / "全球市场总览" / "今日市场行情"
"美股夜盘" / "道琼斯" / "标普500" / "纳斯达克" / "VIX恐慌指数"
"上证指数" / "深证成指" / "创业板" / "恒生指数"
"腾讯控股" / "特斯拉" / "英伟达" / "京东" / "拼多多"
```

### 盘口大单分析（腾讯财经）

```python
from market_quotes import BlockTrade

# 盘口大单（买盘大单/小单、卖盘大单/小单比例）
print(BlockTrade.format_report("sh600519"))   # 茅台
print(BlockTrade.format_report("usTSLA"))     # 特斯拉
```

**触发词**：`"盘口大单"` / `"大单比例"` / `"主力活跃"`

### 资金流向（腾讯财经）

```python
from market_quotes import FundFlow

# ⚠️ 注意：资金流向接口（ff_前缀）对A股个股返回 none_match，
#    该接口可能仅支持部分指数基金。个股资金流建议使用东方财富专项API。
print(FundFlow.format_report("sh600519"))
```

**触发词**：`"资金流向"` / `"主力净流入"`

## 快捷提示词

| 场景 | 提示词 |
|------|--------|
| A股快讯 | 抓取今日A股快讯 |
| 财经早餐 | 财经早餐：A股+宏观+期货，打包成markdown |
| 美股夜盘 | 腾讯财经美股夜盘，道琼斯/标普/纳斯达克/VIX |
| 保存文件 | 生成 ~/finance-news/daily.md，包含东方财富A股+新浪财经宏观快讯 |
| 定时任务 | 每30分钟抓一次A股快讯，保存到 ~/.hermes/finance-news/ |
| 全来源 | 抓取东方财富、新浪财经、同花顺、财联社四源快讯 |

## 来源 → 分类映射

| 分类 | 来源 | 说明 |
|------|------|------|
| A股/港股/美股/期货/宏观 | eastmoney | channel 102/105/106/107/109 |
| 全球宏观/财经 | sina | lid=2516 实时股票快讯 |
| 智能选股 | iwencai | 代理 eastmoney A股 |
| 全部快讯 | cailian | 财联社，电报页面全分类 |

## 输出格式

`NewsItem.to_markdown()` 格式：
```
- [来源] · 分类 · YYYY-MM-DD HH:MM [标题](URL)
```

`FinanceNewsScraper.to_markdown()` 格式：
```
## 📊 财经快讯

### 🗞️ 东方财富
- [东方财富] · A股 · 2026-04-12 09:05 [标题](URL)
...

_Generated at YYYY-MM-DD HH:MM:SS_
```

## 文件结构

```
finance-news/
├── SKILL.md
├── references/
│   └── usage-guide.md    ← 本文件
└── scripts/
    ├── __init__.py
    └── scraper.py
```

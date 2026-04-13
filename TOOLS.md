# TOOLS.md - 环境配置笔记

> 本文件记录工具链、脚本、查询方法，供 Agent 日常使用

---

## 📁 工具目录速查

| 目录 | 用途 |
|------|------|
| `scripts/` | 东方财富API、新闻查询、辅助工具 |
| `scripts/stock_detail.py` | 东方财富详细数据(含融资融券) |
| `scripts/stock_news.py` | 新闻查询 |
| `scripts/eastmoney_api.py` | 东方财富行情API封装 |
| `scripts/eastmoney_stock.py` | 东方财富股票数据 |
| `scripts/market_tools.py` | 大盘资讯工具 |
| `scripts/stats.py` | 胜率统计 |
| `scripts/backtest.py` | 回测脚本 |
| `scripts/wencai_panorama.py` | 问财全景（42函数，整合资金/板块/龙虎榜/组合/融资/复盘） |
| `scripts/trade_entry.py` | 手动成交录入（Version1格式解析→确认→持仓更新） |
| `tools/` | 量化分析工具模块（见下表） |
| `memory/` | 数据存储（持仓、交易、策略） |
| `memory/selections/` | 每日选股记录 |
| `memory/calibration/` | 评分校准记录 |
| `memory/holdings/` | 持仓数据 |
| `memory/market-sentiment/` | 市场情绪数据 |

---

## 🛠️ tools/ 工具模块

| 模块 | 功能 |
|------|------|
| `realtime_data.py` | 腾讯财经实时行情 |
| `market_stats.py` | 大盘涨跌家数统计（问财） |
| `realtime_eastmoney.py` | 东方财富实时行情（备选） |
| `daily_report.py` | 每日早报API |
| `selection_logger.py` | 选股日志自动归档 |
| `backtest_analyzer.py` | 回测统计分析 |
| `position_alert.py` | 持仓预警监控 |
| `realtime_monitor.py` | 高频实时监控 |
| `shareholder_analysis.py` | 股东分析 |
| `stock_analysis.py` | 个股全面分析（量化评分，程序化） |
| `stock_report.py` | **个股深度分析报告**（阅读型/飞书推送，含三档操作情景） |
| `auto_sentiment.py` | **自动情绪评估 + 主线识别** |
| `us_market_monitor.py` | **美股夜盘监控** |
| `news_adapter.py` | **新闻适配器** (news-aggregator skill封装) |
| `search_adapter.py` | **搜索适配器** (multi-search + tavily封装) |
| `sentiment_aggregator.py` | **舆情聚合中心** (多源→打分→存储) |
| `auto_score_record.py` | 持仓评分自动记录 |
| `auto_weight_feedback.py` | 权重自动反馈 |
| `strategy_comparison.py` | 策略对比分析 |
| `t0_monitor.py` | T+0 实时监控 |
| `test_stock_analysis.py` | 测试脚本 |

---

## Git 提交流程

用户说 **"提交quant-claw-skill"** 或 **"同步技能代码"** 时执行：

```bash
# 同步并提交（默认）
~/.agents/skills/quant-claw-skill/tools/git_sync.sh

# 仅拉取远程覆盖本地
~/.agents/skills/quant-claw-skill/tools/git_sync.sh --pull

# 仅提交不同步
~/.agents/skills/quant-claw-skill/tools/git_sync.sh --commit
```

- **源目录**: ~/.agents/skills/quant-claw-skill
- **目标目录**: /home/claw/bench/github/quant-claw-skill
- **远程**: git@github.com:raidery/quant-claw-skill.git

---

## 技能路径

- **问财技能**: wencai

## 查询模板

- 见 `memory/strategy-templates/strategy-templates.json`

## 自选股查询方法

### 文件规则（2026-03-24 更新）

| 文件 | 数量 | 说明 |
|------|------|------|
| `my_favorites.json` | 130只 | 完整版 |
| `my_favorites_top30.json` | 30只 | 精简版 |

### 筛选条件（精简版）

- 5日涨幅 > -5%
- 换手率 > 3%
- 流通市值 30-500亿

### 查询流程

1. 先读取 `my_favorites.json`
2. 可选读取 `my_favorites_top30.json`
3. 若无数据再请求服务器
4. 更新触发：用户说"更新自选股"或"同步自选股"

### 数据结构

```json
{
  "update_time": "2026-03-24T08:05:18",
  "total": 130,
  "stocks": [
    {
      "code": "300345.SZ",
      "name": "华民股份",
      "price": 8.99,
      "change_pct": 20.03,      // 今日涨跌幅
      "turnover": 38.60,        // 换手率
      "volume_ratio": 2.30,     // 量比
      "float_mv": 43.09,        // 流通市值(亿)
      "concept": "...",         // 所属概念(前60字)
      "change_5d": 20.03,       // 5日涨跌幅
      "main_fund": -5274733     // 主力资金(万元)，腾讯API原始数据是万元
    }
  ]
}
```

### 问财查询方法

需要先读取 `.wencai_cookie` 文件，然后调用问财API：

```python
import pywencai

# 读取cookie
with open('.wencai_cookie', 'r') as f:
    cookie = f.read().strip()

# 查询自选股
result = pywencai.get(query='我的自选股', loop=True, cookie=cookie)
```

### 查询示例

```bash
# 查询自选股
python3 query.py "自选股涨幅大于2%"

# 其他自选股查询示例
python3 query.py "自选股 涨跌幅 换手率 量比"
python3 query.py "自选股 主力资金流入"
python3 query.py "自选股 跌幅大于3%"
```

> **注意**：需要同花顺账号绑定，问财才能获取自选股列表。

## Git 提交流程

用户说 **"提交代码"** 或 **"提交代码到github"** 时执行：

```bash
# 1. 同步 workspace 文件到 repo（排除 skills 和 .openclaw 内部状态）
rsync -av --delete \
  /home/claw/.openclaw/workspace-quant-claw/ \
  /home/claw/bench/github/quant-claw/quant-claw-agent/ \
  --exclude='.git' \
  --exclude='skills'

# 2. 清理不需要的目录
cd /home/claw/bench/github/quant-claw/quant-claw-agent
rm -rf .openclaw

# 3. 查看变更
git status
git diff

# 4. 暂存、提交、推送
git add -A
git commit -m "更新配置：$(git diff --cached --name-only | tr '\n' ' ')"
git push
```

## 更新代码流程

用户说 **"更新quant-claw代码"** 或 **"更新到最新代码"** 时执行：

```bash
# 1. 先从 GitHub 拉取最新代码
cd /home/claw/bench/github/quant-claw/quant-claw-agent
git pull

# 2. 同步 repo → workspace（排除 .git 和 .openclaw 内部状态）
rsync -av --delete \
  /home/claw/bench/github/quant-claw/quant-claw-agent/ \
  /home/claw/.openclaw/workspace-quant-claw/ \
  --exclude='.git' \
  --exclude='.openclaw'
```

- **仓库路径**: `/home/claw/bench/github/quant-claw/quant-claw-agent`
- **远程地址**: `git@github.com:raidery/quant-claw.git`
- **分支**: main

## 个股实时行情查询方法

查询持仓股/自选股实时行情（正确姿势）：

```python
import pywencai
result = pywencai.get(query='查询{股票代码}{股票名称}当前股价', loop=True)
data = result.get('历史涨跌幅相关数据')[0]

# 提取关键数据
{
    "现价": data.get('收盘价'),
    "涨跌幅": data.get('涨跌幅'),
    "换手率": data.get('换手率'),
    "开盘价": data.get('开盘价'),
    "最高价": data.get('最高价'),
    "最低价": data.get('最低价'),
    "振幅": data.get('振幅'),
}
```

**注意**：返回格式是 dict，需用 `.get()` 提取，不是 DataFrame。

## 新闻类查询方法

**财联社新闻** → 已由 `auto_sentiment.py` 自动抓取，包含在情绪评估报告中
**重要财经新闻** → 使用 `web_fetch` 命令手动抓取财联社电报：

```bash
web_fetch url="https://www.cls.cn/telegraph" extractMode=text maxChars=6000
```

**分工原则**：
- **问财**：股票筛选、行情数据、技术指标、板块涨幅、解禁数据
- **auto_sentiment.py**：大盘情绪 + 主线识别（全自动，07:00/10:00/13:00 定时执行）
- **web_fetch 财联社**：突发新闻、政策解读、公司公告、外盘动态、地缘事件

### auto_sentiment.py 函数

```python
from tools.auto_sentiment import get_market_hot_report

# 获取市场热点报告（东方财富行业+概念板块排行）
report = get_market_hot_report()
print(report)
```

**get_market_hot_report()** - 数据来源：东方财富行业板块(m:90 t:2) + 概念板块(m:90 t:3)
- 识别主线：涨幅>2%且个股数>10只
- 集成到13:00选股初筛Cron第1步

---

## 📰 舆情聚合系统 (sentiment_aggregator.py)

> 多源舆情 → 量化打分 → 情绪标签

### 模块

| 模块 | 功能 |
|------|------|
| `news_adapter.py` | news-aggregator skill 封装 |
| `search_adapter.py` | multi-search + tavily 封装 |
| `sentiment_aggregator.py` | 舆情聚合主模块 |

### 数据源

| 来源 | 说明 |
|------|------|
| WallStreetCN | 财经新闻 |
| 微博热点 | 社交热点 |
| Tavily AI | 结构化深度搜索 |
| 板块新闻 | AI/新能源/半导体/医药 |

### 情绪打分规则

```python
SENTIMENT_KEYWORDS = {
    "利好": {"政策利好": 2, "业绩增长": 1.5, "并购重组": 2, "获批": 1, "订单": 1},
    "利空": {"业绩下滑": -2, "解禁": -1.5, "监管": -1, "澄清": -0.5, "诉讼": -1},
}
```

### 事件标签

- 政策、业绩、并购、解禁、行业、海外

### 使用方法

```python
from tools import (
    SentimentAggregator,
    run_sentiment_aggregation,
    get_sentiment_report,
)

# 运行舆情聚合
report = run_sentiment_aggregation()

# 获取当前报告
report = get_sentiment_report()

# 使用聚合器
aggregator = SentimentAggregator()
result = aggregator.run()
```

### 输出格式

```json
{
  "fetch_time": "2026-04-04 07:00",
  "date": "2026-04-04",
  "news_sentiment": {
    "items": [...],
    "summary": "一句话舆情摘要",
    "total_score": 0.5,
    "label": "利好偏多",
    "positive_count": 15,
    "negative_count": 5,
    "hot_tags": ["政策", "行业", "业绩"]
  }
}
```

**输出路径**: `memory/market-sentiment/market-sentiment.json`

---

## 问财选股策略查询方法

### 1. 隔夜持股v2.2策略（当前主力）

```python
import pywencai
import pandas as pd

query = '涨幅大于3%且涨幅小于6% 量比大于1.2且量比小于4 换手率大于3%且换手率小于8% 流通市值大于50亿且流通市值小于300亿 收盘价大于5日均线 5日均线大于10日均线 10日均线大于20日均线 20日内有过涨停'
result = pywencai.get(query=query, loop=True)

# 返回的是DataFrame，直接处理
df = result
cols = ['股票简称', '股票代码', '涨跌幅:前复权[YYYYMMDD]', '换手率[YYYYMMDD]', '量比[YYYYMMDD]', 'a股市值(不含限售股)[YYYYMMDD]', '收盘价:不复权[YYYYMMDD]', '技术形态[YYYYMMDD]']
df.columns = ['名称', '代码', '涨跌幅%', '换手率%', '量比', '市值', '现价', '技术形态']
```

### 2. 今日热点v1.0策略

```python
query = '非ST 股价大于5元且股价小于50元 流通市值大于30亿且流通市值小于150亿 涨幅大于1%且涨幅小于7% 量比大于0.8且量比小于5 换手率大于3%且换手率小于15% MACD金叉 DDE大单净额大于0 市场类型非科创板 市场类型非北交所'
result = pywencai.get(query=query, loop=True)
```

### 3. 趋势突破v1.0策略

```python
query = '涨幅大于3%且涨幅小于7% 量比大于1.2 换手率大于3%且换手率小于12% 流通市值大于50亿 收盘价大于20日均线 5日均线大于10日均线 10日均线大于20日均线 20日均线大于60日均线 MACD大于0'
result = pywencai.get(query=query, loop=True)
```

### 4. 获取实时行情

```python
# 方法1：查询语句（推荐）
result = pywencai.get(query='查询{股票代码}{股票名称}当前股价', loop=True)
data = result.get('历史涨跌幅相关数据')[0]

# 提取字段
{
    "现价": data.get('收盘价'),
    "涨跌幅": data.get('涨跌幅'),
    "换手率": data.get('换手率'),
    "最高价": data.get('最高价'),
    "最低价": data.get('最低价'),
    "振幅": data.get('振幅'),
}

# 方法2：直接查询股票代码
result = pywencai.get(query='000049 德赛电池', loop=True)
data = result.get('历史涨跌幅相关数据')
```

---

## 📊 问财全景 (Wencai Panorama)

> `scripts/wencai_panorama.py` | 31个函数 | 6大模块

### 功能概览

| 模块 | 函数 | 说明 |
|------|------|------|
| **资金流向** | 6个函数 + 1个报告 | 主力/大单/行业资金净流入 |
| **板块轮动** | 5个函数 + 1个报告 | 今日/5日/20日板块涨跌 |
| **龙虎榜** | 6个函数 + 1个报告 | 机构/游资/连续买入 |
| **组合查询** | 4个函数 + 1个报告 | 资金+MACD/KDJ/均线组合 |
| **选股功能** | 10个函数 + 1个报告 | 资金×技术面×基本面多维筛选 |
| **融资融券** | 2个函数 + 1个报告 | 融资净买入/卖出排行 |
| **每日复盘** | daily_review | 一键全量复盘 |

### 使用方法

```python
from tools import (
    daily_review,           # 全量复盘（推荐）
    capital_flow_report,    # 资金流向报告
    sector_rotation_report, # 板块轮动报告
    dragon_tiger_report,    # 龙虎榜报告
    combined_query_report,   # 组合查询报告
    margin_report,          # 融资融券报告
    # --- 单项查询 ---
    get_main_fund_flow_top20,   # 主力资金净流入前20
    get_sector_rise_today,      # 今日涨幅前10板块
    get_lhb_institution_buy,    # 龙虎榜机构买入
    get_fund_macd_golden_cross, # 资金+MACD金叉
    stock_selection_report,     # 多维选股报告（推荐）
    get_multi_dimension,         # 全能组合（资金+涨幅+MACD+PE+ROE）
    quick_query,                # 通用快速查询
)

# 一键复盘（最常用）
daily_review()

# 单项查询
df = get_main_fund_flow_top20()
df = get_sector_rise_today(10)
df = get_lhb_institution_buy()

# 通用查询
df = quick_query('今日主力资金净流入前10', head=10)
```

### 命令行用法

```bash
# 全量复盘
python3 scripts/wencai_panorama.py

# 单项报告
python3 scripts/wencai_panorama.py 资金流向
python3 scripts/wencai_panorama.py 板块轮动
python3 scripts/wencai_panorama.py 龙虎榜
python3 scripts/wencai_panorama.py 组合查询
python3 scripts/wencai_panorama.py 选股
```

---

## 常用问财查询语句

| 场景 | 查询语句 |
|------|---------|
| 个股行情 | `查询{代码}{名称}当前股价` |
| 上证指数 | `上证指数行情` |
| 大盘涨跌 | `上证指数涨跌幅` |
| 选股条件 | `涨幅大于3%且涨幅小于6% 量比大于1` |
| 排除ST | `非ST` |

---

## 封装函数库

### 1. 获取个股行情

```python
import pywencai

# 方式1：获取当日行情
result = pywencai.get(query='查询{代码}{名称}当前股价', loop=True)
data = result.get('历史涨跌幅相关数据')[0]

{
    '收盘价': data.get('收盘价'),
    '涨跌幅': data.get('涨跌幅'),
    '最高价': data.get('最高价'),
    '最低价': data.get('最低价'),
    '换手率': data.get('换手率'),
}

# 方式2：获取多日历史行情（最近8天）
data_list = result.get('历史涨跌幅相关数据')
for d in data_list[:5]:  # 取最近5天
    print(f"日期: {d.get('交易日期')}")
    print(f"  收盘价: {d.get('收盘价')}元")
    print(f"  涨跌幅: {d.get('涨跌幅')}%")
```

### 3. 选股策略执行

```python
def run_strategy(query):
    """执行问财选股策略"""
    import pywencai
    import pandas as pd
    
    result = pywencai.get(query=query, loop=True)
    
    if isinstance(result, pd.DataFrame):
        return result
    return None
```

---

## 回测系统

### 目录结构

```
memory/backtest/
├── selections/      # 每日选股记录
│   └── 2026-03-20.json
├── performance/    # 次日表现
│   └── 2026-03-21.json
└── results/       # 回测统计
    └── summary.json
```

### 使用方法

#### 1. 记录选股（选股后自动执行）

当运行策略选出股票后，我会自动记录到 `selections/` 目录：
- 日期、策略名称
- 股票代码、名称、选中价格
- 大盘信息（热点板块等）

#### 2. 更新次日表现

**Prompt**：
```
更新次日表现，日期2026-03-20，开盘价：德赛电池27.80、大叶股份26.50
```

我会：
1. 查询每只股票的收盘价
2. 自动计算收益
3. 保存到 `performance/` 目录

#### 3. 查看回测统计

**Prompt**：
```
查看回测统计
```

返回：
- 总交易次数、胜率、平均收益
- 各策略表现排名
- 牛股捕捉率等

---

## 📊 数据源实践规律（2026-04-07 验证总结）

> 腾讯财经 + 问财 组合覆盖 **90%** 数据需求

### 快速市场概况（已验证脚本）

```python
import pywencai, requests

# 涨停/跌停（问财，30秒内）
up = pywencai.get(query='今日涨停家数', loop=True)
down = pywencai.get(query='今日跌停家数', loop=True)
non_st_up = up[up['股票简称'].str.contains('ST', case=False, na=False, regex=False) == False]
non_st_down = down[down['股票简称'].str.contains('ST', case=False, na=False, regex=False) == False]

# 成交金额（腾讯财经）
url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
total = 0
for line in r.text.strip().split('\n'):
    parts = line.split('"')[1].split('~')
    if len(parts) < 38: continue
    total += float(parts[37]) / 10000  # 万元→亿元
```

### 数据源分工表

| 数据需求 | 最佳来源 | 说明 |
|---------|---------|------|
| 涨停/跌停 | 问财 hithink API | 精确到ST/非ST分类 |

### ⚠️ 腾讯财经 API 字段单位说明

```python
# parts[37] = 成交额（万元），需要 /10000 转亿元
# parts[38] = 换手率（%）
# parts[32] = 涨跌幅（%）
# parts[31] = 涨跌额（元）
# parts[4]  = 昨收价（元）
# parts[3]  = 当前价（元）
```

> ⚠️ 注意：`parts[37]` 是万元单位，不是元。代码中需 `/10000` 转为亿元。
| 指数行情/成交金额 | 腾讯 `qt.gtimg.cn` | 毫秒级，含涨跌额/涨跌幅/成交额 |
| 热点板块/主线识别 | 东方财富 `push2.eastmoney.com` | 行业板块+概念板块排行 |
| 选股策略 | 问财 `pywencai` | 42函数核心能力 |
| 个股新闻 | 财联社 `fetch_cls_news.py` | 解析`__NEXT_DATA__`，稳定可靠 |
| 美股夜盘 | Yahoo代理+腾讯 | `tools/us_market_monitor.py` |
| 大盘指数（实时） | 腾讯财经 | `tools/realtime_data.py` |
| 融资融券 | 东方财富 | `scripts/stock_detail.py` |
| 排行榜（换手率/成交额） | 东方财富 | `scripts/eastmoney_api.py` |

### ⚠️ 已知缺口

**涨跌家数精确值**：所有接口均失败
- 东方财富 `f114/f115` 字段 → 数据不是涨跌家数（量级不合理）
- 深交所/上交所官方 → 403或系统错误
- 问财 → 超时
- **替代方案** ✅：涨停/跌停比（当前22:1）+ 成交额（1.33万亿）= 更好的市场宽度指标

### ⚠️ 使用原则

> **问财为主，腾讯为辅，东方财富补缺**

1. **首选问财**：选股、涨停/跌停、策略查询
2. **腾讯财经辅助**：指数实时行情、成交金额（最快）
3. **东方财富**：热点板块、融资融券、排行榜
4. **数据冲突**：优先信任问财数据

---

## 📈 东方财富A股数据接口

> `scripts/eastmoney_api.py` - 东方财富数据封装

### 功能列表

| 函数 | 功能 | 说明 |
|------|------|------|
| `get_stock_quote` | 个股实时行情 | 现价、涨跌幅、成交量、市值 |
| `get_kline` | K线数据 | 日/周/月线 |
| `get_margin` | 融资融券 | 融资余额、融券余额 |
| `get_money_flow` | 资金流向 | 主力/超大单净流入 |
| `get_ranklist` | 排行榜 | 涨幅/换手率/成交额 |
| `get_index_quote` | 大盘指数 | 上证/深证/创业板 |

### 使用方法

```python
from scripts.eastmoney_api import (
    get_stock_quote, get_kline, get_margin,
    get_ranklist, get_index_quote
)

# 个股行情
quote = get_stock_quote('002025')

# K线（日线）
kline = get_kline('002025', klt=101, limit=5)

# 融资融券
margin = get_margin('002025')

# 涨幅榜
top = get_ranklist('change', 10)

# 大盘指数
index = get_index_quote('1.000001')  # 上证
```

### 命令行
```bash
python3 scripts/eastmoney_api.py
```

### 常用参数

- **股票代码**：自动识别沪深（00/30开头=深圳，60开头=上海）
- **K线类型**：klt=101(日线), 102(周线), 103(月线)
- **指数代码**：1.000001=上证, 0.399001=深证, 0.399006=创业板

---

## 📰 个股新闻查询

### stock_news.py - 新闻消息面

**使用场景**：

| 场景 | 提示词 |
|------|--------|
| 查询个股新闻 | "查询 xxx 股票新闻" |
| 查看消息面 | "xxx 有什么利好/利空" |
| 持仓风险检查 | "检查持仓股 xxx 有没有利空消息" |
| 选股前尽调 | "查询 xxx 公司新闻，看有没有风险" |

**调用方式**：
```python
from scripts.stock_news import get_stock_news, format_stock_news

news = get_stock_news('603659', '璞泰来')
print(format_stock_news(news))
```

**命令行**：
```bash
python3 scripts/stock_news.py 603659 璞泰来
```

---

## 🛠️ tools/ - 问财封装函数

> 基于 pywencai 封装的常用查询工具

### stock_basic.py - 基本面查询

```python
from tools.stock_basic import get_stock_quote, get_stock_finance, get_stock_basic_info

# 查询行情
quote = get_stock_quote("002025", "航天电器")

# 查询财务
finance = get_stock_finance("002025")

# 综合查询
info = get_stock_basic_info("002025", "航天电器")
```

---

## 📈 东方财富股票查询

通过 A股股票代码获取实时行情、基本面、融资融券等数据。

### 脚本位置
```
scripts/eastmoney_stock.py
```

### 使用方法

#### 命令行
```bash
python3 scripts/eastmoney_stock.py 002025
python3 scripts/eastmoney_stock.py 600519
```

#### Python 调用
```python
from scripts.eastmoney_stock import get_stock_data, format_stock_data

# 获取数据
data = get_stock_data('002025')

# 打印格式化结果
print(format_stock_data(data))
```

### 返回字段

| 字段 | 说明 | 单位 |
|------|------|------|
| price | 最新价 | 元 |
| change | 涨跌额 | 元 |
| change_pct | 涨跌幅 | % |
| open | 今开 | 元 |
| pre_close | 昨收 | 元 |
| high | 最高 | 元 |
| low | 最低 | 元 |
| amplitude | 振幅 | % |
| amount | 成交额 | 亿元 |
| volume | 成交量 | 万手 |
| turnover | 换手率 | % |
| total_mv | 总市值 | 亿元 |
| float_mv | 流通市值 | 亿元 |
| pe | 市盈率(TTM) | - |
| pb | 市净率 | - |
| roe | ROE | % |
| rz_balance | 融资余额 | 亿元 |
| rz_buy | 融资买入额 | 亿元 |
| rz_repay | 融资偿还额 | 亿元 |
| pct_5d | 5日涨幅 | % |
| pct_10d | 10日涨幅 | % |
| pct_60d | 60日涨幅 | % |
| pct_ytd | 年初至今涨幅 | % |

### 依赖
```bash
pip install requests
```

> **注意**：需先 `pip install requests`

---

## 🧭 股东人数与筹码分布分析

> 分析股东人数变化、机构持股比例，判断筹码集中度

### 模块位置
```
tools/shareholder_analysis.py
```

### 功能

| 函数 | 说明 |
|------|------|
| `analyze_stock(code, name, scheme)` | 分析单只股票 |
| `ShareholderAnalyzer()` | 完整分析器，支持对比阈值 |

### 使用方法

```python
from tools import analyze_stock, ShareholderAnalyzer

# 1. 快速分析单只股票
result = analyze_stock("000049", "德赛电池")

# 2. 自定义阈值方案
analyzer = ShareholderAnalyzer(threshold_scheme="conservative")  # 保守型
analyzer = ShareholderAnalyzer(threshold_scheme="balanced")     # 平衡型（默认）
analyzer = ShareholderAnalyzer(threshold_scheme="aggressive")  # 激进型

# 3. 对比多只股票
comparison = analyzer.compare_thresholds([
    {"code": "000049", "name": "德赛电池"},
    {"code": "300879", "name": "大叶股份"},
])
```

### 返回字段

| 字段 | 说明 |
|------|------|
| `shareholders` | 股东户数 |
| `shareholder_change_pct` | 较上期变化% |
| `institution_pct` | 机构持股比例 |
| `institution_count` | 机构数量 |
| `avg_holding` | 人均持股数 |
| `score` | 集中度评分 (0-100) |
| `rating` | 评级（高度集中/轻度集中/相对平衡/轻度分散/高度分散） |
| `factors` | 评分因素 |

### 三种阈值方案

| 方案 | 人均持股高 | 人均持股低 | 机构持股高 | 机构持股低 |
|------|-----------|-----------|-----------|-----------|
| 保守型 | 20000 | 5000 | 50% | 20% |
| 平衡型 | 15000 | 8000 | 40% | 30% |
| 激进型 | 10000 | 10000 | 30% | 15% |

### 评分规则

```
score = 股东变化分 + 人均持股分 + 机构持股分 + 连续变化加分

- 股东人数减少: +20分
- 股东人数增加: -20分  
- 人均持股高于阈值: +30分
- 人均持股低于阈值: -20分
- 机构持股高于阈值: +30分
- 机构持股低于阈值: -20分
- 连续2期减少: +20分
- 连续2期增加: -20分
```

### 触发方式

用户说以下内容时调用：
- "查询股东人数"
- "查询筹码分布"
- "分析000049股东"
- "查看德赛电池筹码"

---

## 📡 实时数据获取模块

> 优先使用腾讯财经API，备选东方财富

### 模块位置
```
tools/realtime_data.py
```

### 功能

| 函数 | 说明 |
|------|------|
| `get_stock_price_tengxun(code)` | 获取个股实时行情 |
| `get_index_price_tengxun(code)` | 获取指数行情 |
| `get_market_summary()` | 获取市场整体情况 |
| `get_multiple_stocks(codes)` | 批量获取多只股票 |
| `get_price(code)` | 获取股票现价 |
| `get_change_pct(code)` | 获取股票涨跌幅 |
| `get_sh_index()` | 获取上证指数涨跌幅 |

### 使用方法

```python
from tools import get_price, get_sh_index, get_stock_price_tengxun

# 获取上证涨跌幅
sh = get_sh_index()
print(f"上证: {sh:+.2f}%")

# 获取个股价格
price = get_stock_price_tengxun("002565")
print(f"现价: {price['price']}, 涨跌幅: {price['change_pct']:+.2f}%")

# 批量获取
stocks = get_multiple_stocks(["000049", "300879", "002565"])
for code, data in stocks.items():
    print(f"{code}: {data['price']}")
```

### API来源

| 数据类型 | 优先 | 备选 |
|---------|------|------|
| 实时行情 | 腾讯财经 | 东方财富 |
| 指数行情 | 腾讯财经 | - |
| 分时数据 | 东方财富 | - |

### 腾讯财经接口格式

```
# 个股
https://qt.gtimg.cn/q=sz002565
https://qt.gtimg.cn/q=sh600519

# 指数
https://qt.gtui.cn/q=sh000001  (上证)
https://qt.gtui.cn/q=sz399001  (深证)
https://qt.gtui.cn/q=sz399006  (创业板)
```

---

## 📊 大盘涨跌家数统计（问财）

> 使用问财API查询A股上涨/下跌/平盘家数
> **触发词**："查询大盘上涨下跌家数"、"查询涨跌家数"、"大盘涨跌家数"

### 模块位置
```
tools/market_stats.py
```

### 功能

| 函数 | 说明 |
|------|------|
| `get_market_stats()` | 查询大盘上涨/下跌/平盘家数 |
| `format_market_stats(stats)` | 格式化输出市场统计 |
| `check_market_environment(stats)` | 判断市场环境等级 |

### 使用方法

```python
from tools import get_market_stats, format_market_stats, check_market_environment

# 查询市场统计
stats = get_market_stats()
print(format_market_stats(stats))
# 📊 A股市场概况
# 总股票数: 5486
# 🔴 上涨: 716 家 (13.1%)
# 🟢 下跌: 4746 家 (86.5%)
# ⚪ 平盘: 24 家 (0.4%)

# 判断市场环境
env = check_market_environment(stats)
print(f"市场环境: {env['desc']}")
print(f"操作建议: {env['action']}")
```

### 环境判断等级

| 上涨占比 | 等级 | 操作建议 |
|---------|------|---------|
| ≥55% | bull | 可积极买入，仓位上限30% |
| ≥40% | neutral | 可少量买入，仓位上限20% |
| ≥25% | warning | 谨慎买入，仓位上限10% |
| <25% | sell | 只做风控，不买新票 |
| 下跌>80% | panic | 空仓观望，不开新仓 |

### 数据来源
- 问财API（`.wencai_cookie`）
- 查询条件：涨幅大于0的A股 / 跌幅大于0的A股 / 涨幅等于0的A股
- 自动翻页获取全部数据（loop=True）

---

## 📝 选股记录模块

> 2026-03-24 新增

### 功能
- 保存每日选股记录
- 区分策略选出的股票和用户实际买入的股票
- 查询次日表现，验证策略有效性

### 模块位置
```
memory/selections/YYYY-MM-DD.json
```

### 数据结构
```json
{
  "date": "2026-03-24",
  "market": {...},
  "strategies": {
    "策略名称": {
      "query": "查询条件",
      "candidates": [...],
      "after_14_30_filter": [...]
    }
  },
  "final_recommendations": [...],
  "user_buys": [...],
  "user_sells": [...]
}
```

### 函数

```python
from tools.selection_logger import (
    save_daily_selections,  # 保存选股记录
    load_daily_selections,  # 读取选股记录
    get_next_day_performance,  # 查询次日表现
    format_selection_report,  # 格式化报告
    backfill_all,  # 回填历史T+1表现（2026-03-27新增）
)

# 保存选股记录
save_daily_selections("2026-03-24", data)

# 读取选股记录
data = load_daily_selections("2026-03-24")

# 生成报告
print(format_selection_report(data))

# 回填历史T+1表现（一次性补全错过的cron数据）
backfill_all()
```

### CLI命令

```bash
# 回填所有历史
python3 tools/selection_logger.py backfill

# 回填指定日期
python3 tools/selection_logger.py backfill 2026-03-24
```
```

### 使用场景

| 触发词 | 功能 |
|--------|------|
| "保存今日选股" | 保存当天选股结果 |
| "查看选股记录" | 显示历史选股报告 |
| "查询策略胜率" | 统计策略表现 |
| "今日市场主线识别" / "今日市场主线" | 自动识别今日最强主线板块 |
| "查询主线" / "今日主线是什么" | 同上，获取板块排行 + 主线建议 |

---

## 🔧 OpenClaw Cron 测试方法

> 2026-03-24 经验总结

### 测试Cron任务（手动触发）

```bash
# 列出所有cron任务
openclaw cron list

# 手动触发执行（不带 --due 参数）
openclaw cron run <job-id>

# 示例：触发选股初筛任务
openclaw cron run 08a26024-99ed-4265-ba38-d7816a9aa590

# 查看运行历史
openclaw cron runs --id <job-id> --limit 3

# 修复投递配置（飞书需要指定用户）
openclaw cron edit <job-id> --channel feishu --to "user:ou_878ac96f54a00bd876d36c2523ebbba4"
```

### 常见问题

| 问题 | 解决方法 |
|------|----------|
| `unknown option --force` | 不需要 `--force`，直接 `openclaw cron run <id>` |
| `not-due` | 不带 `--due` 参数，直接执行 |
| `Delivering to Feishu requires target` | 添加 `--to "user:ou_xxx"` |

---

_按需添加设备、API、主机等环境配置_

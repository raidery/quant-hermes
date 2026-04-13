重要规则（2026-04-12）：Browser Use 等付费/重量级工具必须先让用户 review 并同意后才能使用，禁止擅自调用。范围包括：Browser Use 云端 API、付费数据源、额外费用服务。
§
腾讯 qt.gtimg.cn 扩展知识（2026-04-13）：
- 前缀规则：s_=简版(5字段)，不加=完整版(88字段)；sh/sz/hk/us 分别代表上证/深证/港股/美股
- 完整版字段：[3]=现价 [31]=涨跌额 [32]=涨跌幅% [6]=成交量 [7]=成交额（A股/港股/美股通用）
- 简版字段：[3]=现价 [4]=涨跌额 [5]=涨跌幅% [6]=成交量 [7]=成交额
- ff_ 前缀：资金流向数据（仅支持部分指数/ETF，个股返回none_match）
- s_pk 前缀：盘口大单分析（买盘大单/小单、卖盘大单/小单比例）
- 双版本策略：完整版优先(timeout=8s, 50%成功率阈值) → 超时/失败则自动切简版(timeout=5s)
- 高频请求限流，建议间隔1-5秒
- 编码：GBK
§
## 持仓 | 总资产¥51,126 | 301015百洋医药×100@23.72 | 301526国际复材×300@12.79 | 300199翰宇药业×200@21.60 | 603196璞源材料×100@32.41 | 预警：涨≥5%跌≥-3%量能≥1.5倍 | 已平仓：ETF-A500+2.95% 石大胜华-6.4%（必须9:30前挂单教训）
§
## 选股校准权重 | 动量43 支撑阻力28 资金16 趋势13 | 胜率55.6% | 评分≥75优先，<60排除

## 交易铁律 | 1.止损-3%无条件执行 2.涨幅>3%不买 3.持仓≤3只单票≤30% 4.最佳买入14:30后 5.纳指>2%优先半导体 14:30二次确认：涨幅>6%排除，跌幅>-3%放弃

## Skills | quant-claw-skill:~/.hermes/skills/quant-claw-skill/ | finance-news:~/.hermes/skills/quant-research/finance-news/ | quant-strategy:~/.hermes/skills/quant-strategy/ | market-analysis:~/.hermes/skills/quant-research/market-analysis/

## Cron Jobs | c51ec049c4c4 财经早餐07:30 | 0888c2b3f114 选股初筛13:00 | cefc1cfe2e18 14:30二次确认14:30（周一~五）

## 14:30过滤规则 | 涨幅≤6% 且 涨幅≥-3% 且 换手率≤15% | 买入价=现价×0.99 | 止损价=买入价×0.97

## 问财CSV解析 | query.py parts[1]=code parts[2]=name parts[3]=price parts[4]=chg_pct

## Browser Use规则 | 付费/重量级工具必须先让用户review同意后才能使用，禁止擅自调用
§
## 量化系统构建（2026-04-13更新）

### sentiment_analyzer.py 新建
路径: ~/.hermes/skills/quant-research/market-analysis/scripts/sentiment_analyzer.py（26KB）
与 market_scanner.py 互补：scanner取指数/板块，analyzer取情绪/资金/涨跌家数

**模块**：get_limit_up_down、get_advance_decline_sample、get_northbound_flow、get_sector_money_flow、get_yesterday_limit_today、get_us_night、score_sentiment（5维度评分）

**情绪评分权重**：涨停比30% | 涨跌家数25% | 港股20% | 资金流向15% | 昨日涨停10%

### 文件迁移记录
SOUL.md/AGENTS.md/TOOLS.md已迁移，OpenClaw→Hermes Agent框架；self-improving-agent已启用

### 数据源踩坑（2026-04-13）
东方财富push2盘中频繁断；新浪涨跌节点asc=1升序才能取下跌；腾讯港股字段[5]=涨跌幅%；北向资金datacenter-web报表名已变

### Skills目录
quant-claw-skill/quant-research/finance-news/quant-strategy/market-analysis/
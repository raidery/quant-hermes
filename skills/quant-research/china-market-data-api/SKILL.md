---
name: china-market-data-api
description: "Chinese A-stock market data API quick reference — verified working endpoints and known failures as of 2026-04. Use when fetching Chinese market sentiment data (indices, limit up/down, northbound flow, breadth)."
---

# China Market Data API Guide

## Working Endpoints (2026-04 verified)

### 指数行情 — 腾讯财经
```
URL: https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000300,sh000688
编码: GBK
字段: [3]=现价 [31]=涨跌额 [32]=涨跌幅% [6]=成交量 [7]=成交额
前缀: s_=简版(5字段), 不加=完整版(88字段)
```

### 港股指数 — 腾讯财经（含国企/恒生）
```
URL: https://qt.gtimg.cn/q=s_hkHSCEI,s_hkHSI
编码: GBK
字段: [2]=指数代码 [3]=现价 [4]=涨跌额 [5]=涨跌幅% [6]=成交量
⚠️ 关键：[4]=涨跌额，[5]=涨跌幅%，两者不同！
示例解析: parts[5]=-1.15 → 恒生指数 -1.15%
```

### 涨停/跌停数据 — 东方财富
```
URL: https://push2.eastmoney.com/api/qt/clist/get
涨停: pn=1&pz=100&po=1&fid=f3&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23&fields=f2,f3,f12,f14
跌停: pn=1&pz=50&po=0&fid=f3&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23&fields=f2,f3,f12,f14
headers: User-Agent=Mozilla/5.0, Referer=https://quote.eastmoney.com/
⚠️ 盘中（9:30-15:00）基本全断开，盘后/非交易时段可用！
```

### 涨跌家数采样 — 新浪财经
```
URL: https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple
上涨采样: ?page=1&num=3000&sort=changepercent&asc=0&node=hs_a
下跌采样: ?page=1&num=1000&sort=changepercent&asc=1&node=hs_a
⚠️ 关键：asc=0（降序）→ 全正收益；asc=1（升序）→ 全负收益
用法：分别取样后相加估算涨跌比，不能一次取完
返回字段: symbol, name, trade, pricechange, changepercent
```

### 快讯 — 东方财富
```
URL: https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_20_1_.html
解析: var ajaxResult={...} → JSON.parse(ajaxResult.replace('var ajaxResult=', ''))
```

### 美股昨夜 — 腾讯财经
```
URL: https://qt.gtimg.cn/q=usDJI,usINX,usNDX
编码: GBK
字段: [2]=代码 [3]=现价 [4]=涨跌额 [5]=涨跌幅%
⚠️ 美股收盘后次日有效，交易时段数据不稳定
```

## Known Failures (DO NOT use)

| 接口 | 错误 | 原因 |
|------|------|------|
| push2.eastmoney.com (涨停/资金流) | RemoteDisconnected | 盘中全面断开，非仅频率限制 |
| datacenter-web.eastmoney.com (RPT_MUTUAL_MARKET_SH) | 报表配置不存在 | 报表名已变更，需查新API |
| qt.gtimg.cn ff_前缀 | none_match | 仅支持部分指数/ETF，个股返回空 |
| vip.stock.finance.sina.com.cn getHQNodeCount | Service not found | 接口已下线 |
| vip.stock.finance.sina.com.cn getHQNodeDataCount | Service not found | 接口已下线 |
| cls.cn/api/sw | Method Not Allowed | 财联社API需POST |
| vip.stock.finance.sina.com.cn (hs_zt/hs_zte) | [] 空数组 | 昨日涨停节点数据不稳定 |
| 东方财富北向 api/qt/kamt.rtmin/get | {"data":null} | 接口存在但无数据返回 |

## Market Breadth 涨跌家数 — 备用方案

### 方案A（今日验证可用）：新浪采样
```
1. asc=0 取3000条（降序，全正）→ 上涨数 = 样本中正数 count
2. asc=1 取1000条（升序，全负）→ 下跌数 = 样本中负数 count
3. 估算：A股约5300只，上涨比 = up / (up + down)
4. 平盘 = 5300 - up - down
```

### 方案B（东方财富push2，盘中不可用）
```
# 涨跌停比例作为替代指标
# 涨停>跌停 → 多头市场；涨停<跌停 → 空头市场
# 涨停数>30 + 无跌停 → 情绪高潮
```

## Best Practice — 分层获取（盘中优先顺序）

1. **指数/大盘**: 腾讯 qt.gtimg.cn (快、稳，5大指数)
2. **港股/国企**: 腾讯 s_hkHSCEI,s_hkHSI（北向参考）
3. **涨跌家数**: 新浪 getHQNodeDataSimple 采样（估算市场宽度）
4. **涨跌停统计**: 东方财富 push2（⚠️ 盘中大概率断开，用新浪备用）
5. **板块资金流**: 东方财富 push2（⚠️ 盘中断开，可用新浪hot板块替代）
6. **快讯**: 东方财富 newsapi (JSONP解析)
7. **美股**: 腾讯 usDJI/usINX/usNDX（昨夜收盘）
8. **北向资金**: 无直接接口，用港股恒生作为代理

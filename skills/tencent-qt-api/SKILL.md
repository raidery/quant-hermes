---
name: tencent-qt-api
description: 腾讯财经 qt.gtimg.cn 实时行情接口 — 支持 A股/港股/美股/ETF/中概股，含完整版与简版字段差异、资金流向、盘口大单。
category: data-science
tags:
  - quant
  - finance
  - api
  - china-stock
  - hk-stock
  - us-stock
trigger:
  - "腾讯财经"
  - "qt.gtimg"
  - "全球市场"
  - "上证指数"
  - "恒生指数"
  - "美股夜盘"
  - "VIX"
  - "盘口大单"
  - "资金流向"
version: 1.0.0
created: 2026-04-13
---

# Tencent qt.gtimg.cn 接口

腾讯财经公开实时行情接口，**无鉴权、无密钥，直接 GET，GBK 编码**。

## 基础信息

| 项目 | 说明 |
|------|------|
| 根 URL | `https://qt.gtimg.cn/q=` |
| 编码 | **GBK**（必须） |
| 响应格式 | `v_CODE="状态~字段0~字段1~..."` 以 `~` 分割 |
| 分隔符 | 多代码用英文逗号 `,` 分隔，一次请求全量返回 |
| 前缀规则 | `s_`=简版(5字段) `(无)`=完整版(10+字段) |

## 双版本 Fallback 策略（重要实践经验）

```
1. 完整版请求（timeout=8s）
2. 成功数 >= 50% → 直接返回（含成交量/成交额）
3. 成功数 < 50% 或超时 → 自动切简版（timeout=5s）
4. 简版更好则用简版，否则保留完整版结果
```

**为什么不能统一用简版？** 简版缺少成交量/成交额字段，且对美股指数数据可能有差异。
**为什么不能统一用完整版？** 字段多（88个），解析稍慢，且偶有超时。

---

## ⚠️ 关键发现：简版 vs 完整版字段索引完全不同

> **不要假设完整版和简版的字段索引相同！**

| 字段 | 简版 `s_` | 完整版（无前缀） |
|------|----------|----------------|
| 现价 | `[3]` | `[3]` |
| 涨跌额 | **`[4]`** | **`[31]`** |
| 涨跌幅% | **`[5]`** | **`[32]`** |
| 成交量 | - | `[6]` |
| 成交额 | - | `[7]` |

**⚠️ VIX 完整版例外**：VIX（`usVIX`）在完整版中只有 `[3]=当前值`，`[31]/[32]` 为空/0。VIX 涨跌数据建议用简版 `s_usVIX` 的 `[5]`。

**完整版多字段（70-90 字段），关键数据在尾部 `[31]/[32]`，不是 `[4]/[5]`！**

实测发现：
- 上证(完整版) `[4]=3966.17`（昨收价），`[31]=20.05`（涨跌额），`[32]=0.51`（涨跌幅%）
- 道琼斯(完整版) `[4]=48185.80`（盘中最高），`[31]=-269.23`（涨跌额），`[32]=-0.56`（涨跌幅%）

## 代码前缀规则

| 前缀 | 功能 | 示例 |
|------|------|------|
| `sh` | 上证 | `sh000001` |
| `sz` | 深证 | `sz399001`（深成）、`sz399006`（创业板） |
| `hk` | 港股 | `hkHSI`（恒生）、`hk00700`（腾讯控股） |
| `us` | 美股 | `usDJI`（道琼斯）、`usVIX`（VIX恐慌指数） |
| `s_` | 简版（5字段） | `s_sh000001`、`s_usDJI` |
| `ff_` | 资金流向 | `ff_sh600519`（⚠️ 个股返回 none_match） |
| `s_pk` | 盘口大单 | `s_pksh600519` ✅ 实测可用 |

## 完整版常用代码

```python
# A股指数
sh000001  # 上证指数
sz399001  # 深证成指
sz399006  # 创业板指
sh000300  # 沪深300

# 港股指数
hkHSI     # 恒生指数
hkHSTECH  # 恒生科技
hkHSCEI   # 国企指数
hk00700   # 腾讯控股
hk09988   # 阿里巴巴
hk03690   # 美团

# 美股指数
usDJI     # 道琼斯
usINX     # 标普500
usNDX     # 纳斯达克100
usVIX     # VIX恐慌指数（⚠️ 用 usVIX，不是 s_usVIX）

# 美股ETF
usSPY     # 标普500ETF
usQQQ     # 纳指100ETF
usIWM     # 罗素2000ETF

# 美股个股
usAAPL    # 苹果
usTSLA    # 特斯拉
usNVDA    # 英伟达
usMSFT    # 微软
usAMZN    # 亚马逊
usGOOGL   # 谷歌
usMETA    # Meta
usJD      # 京东
usBABA    # 阿里巴巴
usPDD     # 拼多多
usNTES    # 网易
usBIDU    # 百度

# A股个股
sh600519  # 贵州茅台
sz000858  # 五粮液
sh601318  # 中国平安
```

## 完整请求示例

```python
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.qq.com",
}

# 完整版：A股+港股+美股
url = "https://qt.gtimg.cn/q=sh000001,sz399006,hkHSI,usDJI,usVIX"
r = requests.get(url, headers=HEADERS, timeout=10)
r.encoding = "gbk"

for line in r.text.strip().split(";"):
    if "=" not in line or "none_match" in line:
        continue
    code = line.split("=")[0].strip().replace("v_", "")
    raw = line.split('"')[1]
    fields = raw.split("~")

    price = float(fields[3])
    change = float(fields[31])   # 完整版用 [31]
    change_pct = float(fields[32])  # 完整版用 [32]
    volume = int(float(fields[6])) if fields[6] else 0

    print(f"{code}: {price} {change:+.2f} ({change_pct:+.2f}%) 成交量:{volume:,}")
```

## VIX 代码注意

| 格式 | 代码 | 说明 |
|------|------|------|
| 简版 | `s_usVIX` | 返回正常 |
| 完整版 | `usVIX` | ✅ 正确 |
| 错误 | `vix` / `s_vix` | 返回 `none_match` |

## 资金流向（ff_）⚠️

- **A股个股**（如 `ff_sh600519`）返回 `none_match`
- 该接口可能仅支持部分指数基金
- 个股资金流建议使用东方财富专项 API

## 盘口大单（s_pk）✅

```python
# 实测正常
url = "https://qt.gtimg.cn/q=s_pksh600519"
# 返回: [0]=买盘大单% [1]=买盘小单% [2]=卖盘大单% [3]=卖盘小单%
```

## 已知限制

- 高频请求（<1秒）可能被限流，建议 1-5 秒间隔
- 仅实时快照，不提供历史 K 线
- 完整版接口返回 70-90 字段，需确认长度再访问尾部索引

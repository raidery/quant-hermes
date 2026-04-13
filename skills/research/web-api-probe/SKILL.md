---
name: web-api-probe
description: "探测未知/无文档的 Web API 端点的方法论 — 适用于反爬严格的中国金融资讯网站（东方财富、华尔街见闻、同花顺、财联社等）。通过 JS bundle 分析、curl 探测、浏览器 DevTools、Cookie Session 重用等手段发现隐藏 API。"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [api, probe, scraper, web, china, finance, httpx, curl, reverse-engineering]
    category: research
    trigger: "API|探测|反爬|抓取|endpoint|js bundle"
required_packages: [httpx]
---

# Web API Probe Methodology

## 适用场景

网站没有公开 API 文档，需要反向工程发现可用端点。典型场景：
- 中国金融资讯网站（东方财富、华尔街见闻、同花顺等）
- 有严格反爬保护的目标
- 需要绕过 71404 / 403 / 连接重置等错误

## 探测流程（标准顺序）

### Step 1 — 基础 HTTP 探测

```bash
# 检查响应头、状态码、响应体类型
curl -v -L -s "https://TARGET.com" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Accept: application/json" \
  --max-redirs 5 -m 10

# 检查是否返回 JSON（哪怕是错误格式）
curl -s "https://TARGET.com/api/v3/content" \
  -H "Accept: application/json" -m 10
```

### Step 2 — 解析 JS Bundle 找 API Base URL

这是最有效的方法，特别是对 Nuxt/Next.js SSR 应用：

```python
import httpx, re

# 1. 获取主页面 HTML
resp = httpx.get("https://TARGET.com", timeout=15, follow_redirects=True)
html = resp.text

# 2. 提取 JS bundle URL
js_urls = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html)
print(f"Found {len(js_urls)} JS files")

# 3. 下载较大的 JS bundle（通常是主 bundle）
for js_url in js_urls[:5]:
    resp = httpx.get(js_url, headers={"Referer": "https://TARGET.com/"}, timeout=30)
    js_content = resp.text
    
    # 4. 在 JS 中搜索 API 相关字符串
    api_patterns = [
        r'["\'](https?://[^"\']*(?:api|apiv)[^"\']*)["\']',
        r'(?:baseURL|base_uri|API_HOST|apiHost)\s*[:=]\s*["\']([^"\']+)["\']',
        r'["\']([^"\']*\.awst\.com[^"\']*)["\']',
        r'["\']([^"\']*wscn[^"\']*)["\']',
    ]
    for pattern in api_patterns:
        matches = re.findall(pattern, js_content)
        if matches:
            print(f"  Found: {matches[:10]}")
```

**实际案例**：华尔街见闻的 JS bundle `https://static.wscn.net/ivanka-pc/0b10488447e7cc356a3b.js` 揭示了真实 API 域名 `api-one-wscn.awtmt.com`。

### Step 3 — Cookie/Session 重用

很多中国网站需要先访问主站获取 Cookie，再请求 API：

```python
import httpx

with httpx.Client(timeout=15, follow_redirects=True) as client:
    # Step 1: 获取主站 cookie
    r1 = client.get("https://TARGET.com", headers={"User-Agent": "Mozilla/5.0"})
    cookies = dict(r1.cookies)
    print(f"Cookies: {cookies}")
    
    # Step 2: 带 cookie 请求 API
    r2 = client.get(
        "https://API_BASE/v1/content",
        params={"channel": "global", "limit": 5},
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://TARGET.com/",
            "Accept": "application/json",
        }
    )
    print(f"RC={r2.status_code}, body={r2.text[:200]}")
```

### Step 4 — 探测 lid/channel 等查询参数

新浪财经等使用数字 ID（lid）区分新闻分类，需要枚举探测：

```python
import httpx

test_lids = {
    "2514": "财经要闻（旧）",
    "2516": "股票快讯",
    "2517": "产经",
    "2218": "港股",
    "169": "期货",
}

headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://TARGET.com/"}
for lid, name in test_lids.items():
    resp = httpx.get(
        "https://feed.mix.sina.com.cn/api/roll/get",
        params={"pageid": "153", "lid": lid, "num": 3, "page": 1},
        headers=headers, timeout=5
    )
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("result", {}).get("data", [])
        if items:
            ctime = items[0].get("ctime", "")
            print(f"lid={lid} ({name}): count={len(items)}, latest_ts={ctime}")
```

**验证时间戳**：用 `datetime.fromtimestamp(int(ctime))` 确认数据是否为最新，lid=2514 可能是旧数据存档。

### Step 5 — 浏览器 DevTools 拦截

如果以上都失败，用浏览器手动查看 Network 面板：

```javascript
// 在浏览器控制台拦截所有 fetch/XHR
const origFetch = window.fetch;
window._apiCalls = [];
window.fetch = function(...args) {
  const url = typeof args[0] === 'string' ? args[0] : args[0].url;
  if (url.includes('api') || url.includes('json')) {
    window._apiCalls.push({url, method: 'fetch'});
  }
  return origFetch.apply(window, args);
};
setTimeout(() => JSON.stringify(window._apiCalls), 5000);
```

## 中国金融网站已知坑

| 网站 | 问题 | 发现方法 |
|------|------|----------|
| 华尔街见闻 | JS bundle 揭示 API 域名 `api-one-wscn.awtmt.com`，所有路径返回 71404，已废弃 | JS bundle 分析 → 放弃 |
| 新浪财经 | lid=2514 是旧存档数据，lid=2516 才是实时 | 时间戳验证 |
| 同花顺 | 无独立公开 API，代理东方财富 | 探测失败 |
| 东方财富 | 快讯 API 格式为 `var ajaxResult={...}` 需正则提取 | curl 探测 |
| 财联社 | 纯客户端 Next.js 渲染，`__NEXT_DATA__` 由 JS 注入 HTML，curl 拿不到 | 浏览器 console / Browser Use |

## 关键 Header 参考

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://TARGET.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://TARGET.com/",
    "x-ucapp-ua": "Mozilla/5.0",  # 某些阿里系网站需要
}
```

## 财联社特别说明

**结论（更新 2026-04-12）：可以直接 HTTP 采集，不需要 Browser Use！**

财联社 `https://www.cls.cn/telegraph` 的 `window.__NEXT_DATA__` **确实存在于 HTML 源码里**，由服务端预渲染（SSR）注入，不是纯客户端 JS 注入。用 `requests` + `BeautifulSoup` 即可提取：

```python
import requests
from bs4 import BeautifulSoup
import json

headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
           "Referer": "https://www.cls.cn/"}
resp = requests.get("https://www.cls.cn/telegraph", headers=headers, timeout=15)

soup = BeautifulSoup(resp.text, "html.parser")
scripts = soup.find_all("script")
json_text = None
for s in scripts:
    txt = s.string or ""
    if "telegraphList" in txt and len(txt) > 1000:
        json_text = txt
        break

data = json.loads(json_text)
items = data["props"]["initialState"]["telegraph"]["telegraphList"]
# items[i]["title"], items[i]["ctime"], items[i]["subjects"][0]["subject_name"], items[i]["shareurl"]
```

字段映射：
- `title` — 标题
- `ctime` — Unix 时间戳（秒），需 `datetime.fromtimestamp(int(ctime))`
- `subjects[0]["subject_name"]` — 分类（如"A股""中东冲突"）
- `shareurl` — 文章 URL
- `reading_num` — 阅读数
- `brief` — 摘要/导语

旧版 `/api/sw` API（`POST https://www.cls.cn/api/sw`）返回 `{"error":"签名错误"}`，已废弃，无需再探。

## 常见错误码

| 错误码 | 含义 | 处理 |
|--------|------|------|
| 71404 | 端点不存在或需要特殊认证 | 换路径或放弃 |
| 403 | IP/区域限制 | 换 IP 或用代理 |
| 连接重置 | 被防火墙拦截 | 换 User-Agent / Cookie |
| 60 | SSL 证书问题 | 忽略证书验证（测试用）|
| 签名错误 | 私有 API 需要签名验证 | 放弃，改用 Browser Use |

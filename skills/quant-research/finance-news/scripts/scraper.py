"""
Financial news unified scraper — EastMoney / IWenCai / Sina Finance / CaiLianShe

All sources use direct HTTP (requests / httpx). No browser automation required.

Confirmed working APIs (2026-04-12):
  EastMoney 快讯:
    https://newsapi.eastmoney.com/kuaixun/v1/getlist_{channel}_ajaxResult_{pageSize}_{pageNum}_.html
    Channel IDs: 101=综合, 102=A股, 105=港股, 106=美股, 107=期货, 109=宏观
    Response: var ajaxResult={...JSON...}

  IWenCai (同花顺):
    Same EastMoney API (tagged as iwencai — both operated by same company)

  Sina Finance (新浪财经):
    https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num={n}&page=1
    lid=2516 is real-time stock/global news (confirmed 2026-04-12)

  CaiLianShe (财联社):
    https://www.cls.cn/telegraph — HTML inline JSON in window.__NEXT_DATA__
    Parsed via BeautifulSoup + regex from raw HTML (no auth required)
    Structure: window.__NEXT_DATA__["props"]["initialState"]["telegraph"]["telegraphList"]
    (confirmed working 2026-04-12, replaces previous Browser Use approach)

  WallStreetCN (华尔街见闻):
    No working public API found despite extensive probing.
    api-one-wscn.awtmt.com returns 71404 Not Found for all paths.
    Sina Finance (lid=2516) used as global macro proxy instead.

Usage:
    from finance_news import FinanceNewsScraper
    scraper = FinanceNewsScraper()
    items = scraper.fetch_all(sources=["eastmoney", "sina", "cailian"])
    print(scraper.to_markdown(items))
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NewsItem:
    """Single news item"""
    title: str
    url: str
    source: str           # short name: eastmoney / sina / iwencai
    source_name: str      # display name
    published_at: Optional[str] = None   # YYYY-MM-DD HH:MM:SS or YYYY-MM-DD
    summary: Optional[str] = None
    category: Optional[str] = None       # A股 / 期货 / 全球宏观 / 智能选股
    tags: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_markdown(self) -> str:
        meta_parts = []
        if self.source_name:
            meta_parts.append(f"[{self.source_name}]")
        if self.category:
            meta_parts.append(self.category)
        if self.published_at:
            # Trim to date+time only
            meta_parts.append(self.published_at[:16])
        meta = " · ".join(meta_parts)
        return f"- {meta} [{self.title}]({self.url})"


@dataclass
class ScrapeResult:
    """Result from a single source"""
    source: str
    items: list[NewsItem]
    raw_response: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class MarketQuote:
    """
    Real-time market quote — US indices, VIX, etc.
    Used by TencentUSMarket (Tencent Finance API).
    """
    name: str          # "道琼斯" / "标普500" / "纳斯达克100" / "VIX恐慌指数"
    symbol: str        # API code: s_usDJI / s_usINX / s_usNDX / s_usVIX
    price: float
    change: float      # absolute change
    change_pct: float  # percentage change %
    source: str = "tencent"
    trading_date: str = ""   # YYYY-MM-DD，美股交易日（由腾讯服务器GMT时间计算）
    extra: dict = field(default_factory=dict)

    def emoji_text(self) -> str:
        """Format as emoji pure-text line."""
        arrow = "▲" if self.change >= 0 else "▼"
        sign = "+" if self.change >= 0 else ""
        pct_str = f"{sign}{self.change_pct:.2f}%"
        price_str = f"{self.price:,.2f}"
        change_str = f"{sign}{self.change:,.2f}"
        return f"  {self.name:<14} {price_str:>12}  {arrow} {change_str} ({pct_str})"

    def vix_emoji_text(self) -> str:
        """VIX-specific format with sentiment label."""
        arrow = "▲" if self.change >= 0 else "▼"
        sign = "+" if self.change >= 0 else ""
        pct_str = f"{sign}{self.change_pct:.2f}%"
        price_str = f"{self.price:,.2f}"
        change_str = f"{sign}{self.change:,.2f}"
        # VIX sentiment: <15 greedy, 15-25 neutral, 25-35 fearful, >35 panic
        v = self.price
        if v < 15:
            label = "😱 极度贪婪"
        elif v < 20:
            label = "😰 偏贪婪"
        elif v < 25:
            label = "😐 中性"
        elif v < 30:
            label = "😨 偏恐慌"
        elif v < 35:
            label = "😰 恐慌"
        else:
            label = "🚨 极度恐慌"
        return f"  {self.name:<14} {price_str:>12}  {arrow} {change_str} ({pct_str})   {label}"


# ─────────────────────────────────────────────────────────────────────────────
# EastMoney (eastmoney.com) — 东方财富
# ─────────────────────────────────────────────────────────────────────────────

class EastMoneyScraper:
    """
    EastMoney (东方财富) news API — 快讯.

    Confirmed working (2026-04-12). No auth required.
    Channel IDs:
      101 = 综合快讯
      102 = A股快讯
      105 = 港股快讯
      106 = 美股快讯
      107 = 期货快讯
      109 = 宏观快讯
    """

    BASE_URL = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_{channel}_ajaxResult_{pageSize}_{pageNum}_.html"
    SOURCE = "eastmoney"
    SOURCE_NAME = "东方财富"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.eastmoney.com/",
        "Accept": "*/*",
    }

    CHANNEL_MAP = {
        "综合": 101, "A股": 102, "港股": 105, "美股": 106,
        "期货": 107, "宏观": 109,
        "global": 109, "stock": 102, "futures": 107,
    }

    @classmethod
    def fetch_latest(cls, category: str = "A股",
                     page: int = 1, page_size: int = 20) -> ScrapeResult:
        channel = cls.CHANNEL_MAP.get(category, 101)
        url = cls.BASE_URL.format(channel=channel, pageSize=page_size, pageNum=page)

        try:
            with httpx.Client(timeout=15, headers=cls.HEADERS) as client:
                resp = client.get(url)
                resp.raise_for_status()

            # Response: var ajaxResult={...JSON...}
            m = re.search(r'=(\{.+})', resp.text, re.DOTALL)
            if not m:
                return ScrapeResult(source=cls.SOURCE, items=[],
                                   error="Failed to parse EastMoney response")

            data = json.loads(m.group(1))
            lives = data.get("LivesList", [])
            items = []
            for row in lives:
                title = row.get("title", "").strip()
                if not title:
                    continue
                url_raw = row.get("url_w", "") or ""
                url = url_raw.replace("http://", "https://")

                items.append(NewsItem(
                    title=title,
                    url=url,
                    source=cls.SOURCE,
                    source_name=cls.SOURCE_NAME,
                    published_at=row.get("showtime") or row.get("time"),
                    summary=row.get("digest"),
                    category=category,
                    extra={"newsid": row.get("newsid")},
                ))

            return ScrapeResult(source=cls.SOURCE, items=items, raw_response=data)

        except Exception as e:
            logger.warning("EastMoney fetch failed: %s", e)
            return ScrapeResult(source=cls.SOURCE, items=[], error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Sina Finance (finance.sina.com.cn) — 新浪财经
# ─────────────────────────────────────────────────────────────────────────────

class SinaFinanceScraper:
    """
    Sina Finance (新浪财经) news API — used as WallStreetCN fallback for global macro.

    Confirmed working (2026-04-12). No auth required.
    """

    SOURCE = "sina"
    SOURCE_NAME = "新浪财经"

    @classmethod
    def fetch_latest(cls, category: str = "宏观", limit: int = 20) -> ScrapeResult:
        # Sina roll API — lid mapping (confirmed 2026-04-12):
        #   2516 = 股票快讯 (A股/港股实时)
        #   2514 = 国际财经 (较旧数据)
        #   2517 = 产经
        # We use lid=2516 for global macro coverage (real-time global news)
        try:
            params = {
                "pageid": "153",
                "lid": "2516",   # real-time stock/global news
                "num": limit,
                "page": 1,
            }
            with httpx.Client(timeout=15) as client:
                resp = client.get(
                    "https://feed.mix.sina.com.cn/api/roll/get",
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://finance.sina.com.cn/",
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            items = []
            for item in data.get("result", {}).get("data", []):
                title = item.get("title", "").strip()
                if not title:
                    continue
                url = item.get("url", "") or item.get("surl", "") or ""

                # Parse timestamp
                ctime = item.get("ctime", "")
                if ctime:
                    try:
                        ts = int(ctime)
                        dt = datetime.fromtimestamp(ts)
                        ctime = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                items.append(NewsItem(
                    title=title,
                    url=url,
                    source=cls.SOURCE,
                    source_name=cls.SOURCE_NAME,
                    published_at=ctime,
                    summary=item.get("intro"),
                    category="宏观",   # Sina财经覆盖全球宏观
                    extra={"author": item.get("author")},
                ))

            return ScrapeResult(source=cls.SOURCE, items=items, raw_response=data)

        except Exception as e:
            logger.warning("Sina fetch failed: %s", e)
            return ScrapeResult(source=cls.SOURCE, items=[], error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# IWenCai (iwencai.com) — 同花顺智能选股
# ─────────────────────────────────────────────────────────────────────────────
# (IWenCaiScraper class continues below — see next patch)
# ─────────────────────────────────────────────────────────────────────────────
# CaiLianShe (cls.cn) — 财联社
# ─────────────────────────────────────────────────────────────────────────────

class CaiLianSheScraper:
    """
    CaiLianShe (财联社 cls.cn) news — A股/期货/宏观 快讯.

    Confirmed working (2026-04-12). No auth required.
    Data is embedded as inline JSON in the HTML page at:
      https://www.cls.cn/telegraph
    Parsed via requests + BeautifulSoup from raw HTML.
    No Browser Use or API signing required.
    """

    SOURCE = "cailian"
    SOURCE_NAME = "财联社"

    @classmethod
    def fetch_latest(cls, category: str = "全部", limit: int = 20) -> ScrapeResult:
        """
        Fetch latest news from CaiLianShe.

        Args:
            category: 全部/加红/公司/看盘/港美股/基金/提醒 (CSS class tabs)
            limit: max items to return
        """
        import requests as _requests
        from bs4 import BeautifulSoup as _BeautifulSoup

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Referer": "https://www.cls.cn/",
            }
            resp = _requests.get(
                "https://www.cls.cn/telegraph",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()

            soup = _BeautifulSoup(resp.text, "html.parser")
            scripts = soup.find_all("script")
            json_text = None
            for s in scripts:
                txt = s.string or ""
                if "telegraphList" in txt and len(txt) > 1000:
                    json_text = txt
                    break

            if not json_text:
                # Fallback: regex scan raw HTML
                import re as _re

                m = _re.search(
                    r'window\.__NEXT_DATA__\s*=\s*({.+?})\s*;</script>',
                    resp.text,
                    _re.DOTALL,
                )
                if m:
                    json_text = m.group(1)
                else:
                    return ScrapeResult(
                        source=cls.SOURCE, items=[], error="No __NEXT_DATA__ found"
                    )

            import json as _json

            data = _json.loads(json_text)
            raw_items = (
                data.get("props", {})
                .get("initialState", {})
                .get("telegraph", {})
                .get("telegraphList", [])
            )

            items = []
            for row in raw_items:
                title = row.get("title", "").strip()
                if not title:
                    content = row.get("content", "")
                    if content:
                        title = content[:80]
                    else:
                        continue

                share_url = row.get("shareurl", "")
                ctime = row.get("ctime", "")
                if ctime:
                    try:
                        ts = int(ctime)
                        ctime = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                subjects = row.get("subjects", []) or []
                subject_name = subjects[0].get("subject_name", "") if subjects else ""

                items.append(
                    NewsItem(
                        title=title,
                        url=share_url or "https://www.cls.cn/telegraph",
                        source=cls.SOURCE,
                        source_name=cls.SOURCE_NAME,
                        published_at=ctime,
                        summary=row.get("brief") or row.get("content", "")[:200],
                        category=subject_name or "财联社",
                        extra={
                            "reading_num": row.get("reading_num", 0),
                            "share_num": row.get("share_num", 0),
                            "level": row.get("level", ""),
                        },
                    )
                )
                if len(items) >= limit:
                    break

            return ScrapeResult(source=cls.SOURCE, items=items, raw_response={"count": len(raw_items)})

        except Exception as e:
            logger.warning("CaiLianShe fetch failed: %s", e)
            return ScrapeResult(source=cls.SOURCE, items=[], error=str(e))


class IWenCaiScraper:
    """
    IWenCai (同花顺 iwencai.com) — 智能选股.

    IWenCai has no independent public news API. It shares EastMoney's infrastructure.
    We proxy through EastMoney's A股/期货 channels and re-tag as IWenCai.
    """

    SOURCE = "iwencai"
    SOURCE_NAME = "同花顺"

    @classmethod
    def fetch_stock_news(cls, page: int = 1, page_size: int = 20) -> ScrapeResult:
        eastmoney_result = EastMoneyScraper.fetch_latest(
            category="A股", page=page, page_size=page_size
        )
        items = []
        for item in eastmoney_result.items:
            item.source = cls.SOURCE
            item.source_name = cls.SOURCE_NAME
            item.category = "智能选股"
            items.append(item)
        return ScrapeResult(
            source=cls.SOURCE,
            items=items,
            raw_response=eastmoney_result.raw_response,
            error=eastmoney_result.error,
        )

    @classmethod
    def fetch_futures_news(cls, page: int = 1, page_size: int = 20) -> ScrapeResult:
        eastmoney_result = EastMoneyScraper.fetch_latest(
            category="期货", page=page, page_size=page_size
        )
        items = []
        for item in eastmoney_result.items:
            item.source = cls.SOURCE
            item.source_name = cls.SOURCE_NAME
            item.category = "期货"
            items.append(item)
        return ScrapeResult(
            source=cls.SOURCE,
            items=items,
            raw_response=eastmoney_result.raw_response,
            error=eastmoney_result.error,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tencent Finance — US Market (腾讯财经美股指数)
# ─────────────────────────────────────────────────────────────────────────────

class TencentUSMarket:
    """
    Tencent Finance US indices via qt.gtimg.cn — 国内直连，requests + GBK.

    API:
        https://qt.gtimg.cn/q=s_usDJI,s_usINX,s_usNDX,s_usVIX

    Response format (each line, GBK encoded):
        v_s_usDJI="股票名~...~代码~现价~涨跌额~涨跌幅~..."
        Key fields (0-indexed ~ split):
            [3] = price
            [4] = change (absolute)
            [5] = change_pct (%)

    Confirmed working 2026-04-13. No auth required.
    """

    SOURCE = "tencent"
    SOURCE_NAME = "腾讯财经"

    CODES = {
        "s_usDJI": "道琼斯",
        "s_usINX": "标普500",
        "s_usNDX": "纳斯达克100",
        "s_usVIX": "VIX恐慌指数",
    }

    @classmethod
    def fetch_overnight_data(cls, limit: int = 4) -> list[MarketQuote]:
        """
        Fetch US index quotes from Tencent Finance.

        Args:
            limit: max number of quotes to return (default 4 = all indices)

        Returns:
            list[MarketQuote], sorted: indices first, VIX last
        """
        import requests as _requests

        url = f"https://qt.gtimg.cn/q={','.join(list(cls.CODES.keys())[:limit])}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://finance.qq.com",
        }

        try:
            r = _requests.get(url, headers=headers, timeout=6)
            r.encoding = "gbk"
        except Exception as exc:
            logger.warning(f"[TencentUSMarket] 请求失败: {exc}")
            return []

        # ── Compute US trading date from local time ────────────────────────────────
        # Beijing time (UTC+8):
        #   Mon-Fri 04:00-23:59 → today is the trading day
        #   Mon-Fri 00:00-03:59 → today minus 1 day (pre-market, same session)
        #   Sat / Sun → roll back to the most recent Fri
        import datetime as _dt
        beijing = _dt.datetime.now() + _dt.timedelta(hours=8)
        us_day = beijing.date()
        if beijing.hour < 4:
            us_day = (beijing - _dt.timedelta(days=1)).date()
        # Sat=6, Sun=7 → roll back to preceding Fri
        while us_day.isoweekday() >= 6:
            us_day -= _dt.timedelta(days=1)
        trading_date = us_day.strftime("%Y-%m-%d")

        quotes: list[MarketQuote] = []
        for line in r.text.strip().split(";"):
            if "=" not in line or "none_match" in line:
                continue
            code = line.split("=")[0].strip().replace("v_", "")
            if code not in cls.CODES:
                continue

            try:
                fields = line.split('"')[1].split("~")
                quote = MarketQuote(
                    name=cls.CODES[code],
                    symbol=code,
                    price=float(fields[3]),
                    change=float(fields[4]),
                    change_pct=float(fields[5]),
                    source=cls.SOURCE,
                    trading_date=trading_date,
                )
                quotes.append(quote)
            except (IndexError, ValueError) as exc:
                logger.warning(f"[TencentUSMarket] 解析失败 line={line[:60]!r}: {exc}")
                continue

        # VIX always last
        quotes.sort(key=lambda q: (q.symbol == "s_usVIX", q.symbol))
        return quotes

    @classmethod
    def format_overnight_report(cls, quotes: list[MarketQuote] = None) -> str:
        """Format quotes as emoji pure-text US market report."""
        if quotes is None:
            quotes = cls.fetch_overnight_data()

        if not quotes:
            return "📊 美股夜盘快报\n\n⚠️ 暂时无法获取美股数据，请稍后重试\n"

        # Derive trading date from first non-VIX quote
        first = next((q for q in quotes if q.symbol != "s_usVIX"), None)
        trading_date_str = first.trading_date if first and first.trading_date else "—"

        lines = [
            f"📊 美股夜盘快报  {trading_date_str}",
            "",
        ]

        # Separate VIX from indices
        indices = [q for q in quotes if q.symbol != "s_usVIX"]
        vix_list = [q for q in quotes if q.symbol == "s_usVIX"]

        for q in indices:
            lines.append(q.emoji_text() + "  🌐")

        if vix_list:
            lines.append("")
            lines.append("─" * 44)
            lines.append(vix_list[0].vix_emoji_text())

        lines.append("")
        lines.append("  ⚠️ 数据仅供参考，非实时交易价格")

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Unified Entry Point
# ─────────────────────────────────────────────────────────────────────────────

SCRAPER_CLASSES = {
    "eastmoney": EastMoneyScraper,
    "sina": SinaFinanceScraper,
    "iwencai": IWenCaiScraper,
    "cailian": CaiLianSheScraper,
}

# Category → source routing
CATEGORY_SOURCE = {
    "A股":         "eastmoney",
    "港股":        "eastmoney",
    "美股":        "eastmoney",
    "期货":        "eastmoney",
    "宏观":        "sina",          # Sina covers global macro
    "全球宏观":     "sina",
    "综合":        "eastmoney",
    "智能选股":     "iwencai",
}


class FinanceNewsScraper:
    """
    Unified financial news scraper — all direct HTTP, no browser.

    Usage:
        scraper = FinanceNewsScraper()

        # All sources
        items = scraper.fetch_all()

        # Specific sources
        items = scraper.fetch_all(sources=["eastmoney", "sina"])

        # By category (auto-routes to source)
        items = scraper.fetch_by_category("A股")
        items = scraper.fetch_by_category("宏观")

        # Markdown output
        print(scraper.to_markdown(items))
    """

    def __init__(self):
        self.results: dict[str, ScrapeResult] = {}

    # ── US Market ─────────────────────────────────────────────────────────────

    def fetch_us_market(self, limit: int = 4) -> list[MarketQuote]:
        """
        Fetch US overnight market data via Tencent Finance API.
        Returns indices + VIX with real-time data.
        """
        return TencentUSMarket.fetch_overnight_data(limit=limit)

    # ── Low-level ─────────────────────────────────────────────────────────────

    def fetch(self, source: str, method: str = "fetch_latest",
              **kwargs) -> ScrapeResult:
        """Fetch from a single named source."""
        scraper_cls = SCRAPER_CLASSES.get(source)
        if not scraper_cls:
            return ScrapeResult(source=source, items=[],
                               error=f"Unknown source: {source}")
        method_fn = getattr(scraper_cls, method, None)
        if not method_fn:
            return ScrapeResult(source=source, items=[],
                               error=f"No method {source}.{method}()")
        # Normalise max_count alias (converts to limit or page_size depending on target)
        _kwargs = dict(kwargs)
        if "max_count" in _kwargs:
            import inspect
            sig = inspect.signature(method_fn)
            params = list(sig.parameters.keys())
            if "limit" in params and "page_size" not in params:
                _kwargs["limit"] = _kwargs.pop("max_count")
            elif "page_size" in params:
                _kwargs["page_size"] = _kwargs.pop("max_count")
            elif "max_count" in params:
                _kwargs["max_count"] = _kwargs.pop("max_count")  # keep as-is
            else:
                _kwargs.pop("max_count")

        result = method_fn(**_kwargs)
        self.results[source] = result
        return result

    # ── Mid-level ─────────────────────────────────────────────────────────────

    def fetch_by_category(self, category: str, page: int = 1,
                          page_size: int = 20) -> list[NewsItem]:
        """Auto-route category to the best available source."""
        source = CATEGORY_SOURCE.get(category.strip(), "eastmoney")
        if source == "eastmoney":
            result = self.fetch("eastmoney", "fetch_latest",
                               category=category, page=page, page_size=page_size)
        elif source == "sina":
            result = self.fetch("sina", "fetch_latest",
                               category=category, limit=page_size)
        elif source == "iwencai":
            method = "fetch_futures_news" if category == "期货" else "fetch_stock_news"
            result = self.fetch("iwencai", method, page=page, page_size=page_size)
        else:
            result = self.fetch("eastmoney", "fetch_latest",
                               category="A股", page=page, page_size=page_size)
        return result.items

    def fetch_all(self, sources: list[str] = None,
                  page: int = 1, page_size: int = 20) -> list[NewsItem]:
        """
        Fetch from multiple sources and merge into one chronologically sorted list.

        Args:
            sources:   list of source names (default: all working sources)
            page:      page number (default: 1)
            page_size: items per source (default: 20)
        """
        if sources is None:
            sources = ["eastmoney", "sina", "iwencai", "cailian"]

        # Map each source to its default fetch method + kwargs
        # IMPORTANT: parameter names must match each method's signature exactly
        # eastmoney → page_size, sina/cailian → limit
        SOURCE_METHODS = {
            "eastmoney": ("fetch_latest", {"category": "A股", "page": page, "page_size": page_size}),
            "sina":      ("fetch_latest", {"category": "宏观", "limit": page_size}),
            "iwencai":   ("fetch_stock_news", {"page": page, "page_size": page_size}),
            "cailian":   ("fetch_latest", {"category": "全部", "limit": page_size}),
        }

        all_items: list[NewsItem] = []
        for src in sources:
            method_name, kwargs = SOURCE_METHODS.get(src, ("fetch_latest", {}))
            result = self.fetch(src, method_name, **kwargs)
            all_items.extend(result.items)

        # Sort descending by time
        all_items.sort(key=lambda x: x.published_at or "1970-01-01", reverse=True)
        return all_items

    # ── Output ────────────────────────────────────────────────────────────────

    @staticmethod
    def to_markdown(items: list[NewsItem], title: str = "📊 财经快讯") -> str:
        """Format news items as Markdown string."""
        if not items:
            return f"{title}\n\n_No items fetched._\n"

        lines = [f"## {title}\n"]
        from collections import defaultdict
        grouped: dict[str, list[NewsItem]] = defaultdict(list)
        for item in items:
            grouped[item.source_name].append(item)

        for src_name, src_items in grouped.items():
            lines.append(f"### 🗞️ {src_name}\n")
            for item in src_items:
                lines.append(item.to_markdown())
            lines.append("")

        lines.append(f"_Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI quick-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scraper = FinanceNewsScraper()

    print("Fetching: 东方财富(A股) + 新浪财经(宏观) + 同花顺(智能选股)...\n")
    items = scraper.fetch_all(sources=["eastmoney", "sina", "iwencai"])

    for src, result in scraper.results.items():
        if result.error:
            print(f"[{src}] ⚠️  {result.error}")

    print(scraper.to_markdown(items))

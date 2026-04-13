"""
Global market quotes via Tencent Finance qt.gtimg.cn.

Supported markets (完整版，无 s_ 前缀):
  - A股指数:  sh000001(上证) sz399001(深证) sz399006(创业板) sh000300(沪深300)
  - 港股指数: hkHSI(恒生) hkHSTECH(恒生科技) hkHSCEI(国企指数)
  - 美股指数: usDJI(道琼斯) usINX(标普500) usNDX(纳斯达克100) usVIX(VIX)
  - 美股ETF:  usSPY usQQQ usIWM
  - 美股个股: usAAPL usTSLA usNVDA usMSFT usAMZN usGOOGL usMETA
  - 中概股:   usJD usBABA usPDD usNTES usBIDU
  - 港股个股: hk00700 hk09988 hk03690(美团) hk09888(阿里云)
  - A股个股:  sh600519 sh000858 sh601318

Response format (GBK encoded):
  v_CODE="状态~名称~代码~现价~涨跌额~涨跌幅~成交量~成交额~..."
  港美: 10 fields  A股: 12 fields
  Key: [3]=price [4]=change [5]=change_pct [6]=volume [7]=turnover

文档: https://qt.gtimg.cn/q=代码1,代码2,...
  s_ 前缀 = 简版(5字段)   无前缀 = 完整版(10字段)
  ff_ 前缀 = 资金流向     s_pk 前缀 = 盘口大单

Confirmed working 2026-04-13. No auth required.
"""

import logging
import requests
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MarketQuote:
    """Single market quote."""
    name: str        # display name
    symbol: str      # API code (no s_ prefix)
    price: float
    change: float    # absolute change
    change_pct: float
    market: str = ""   # A股/港股/美股
    source: str = "tencent"
    trading_date: str = ""
    volume: int = 0     # 成交量（股数）
    turnover: float = 0 # 成交额（元/美元）
    extra: dict = field(default_factory=dict)

    def emoji_text(self) -> str:
        arrow = "▲" if self.change >= 0 else "▼"
        sign = "+" if self.change >= 0 else ""
        pct_str = f"{sign}{self.change_pct:.2f}%"
        price_str = f"{self.price:,.2f}"
        change_str = f"{sign}{self.change:,.2f}"
        return (f"  {self.name:<16} {price_str:>12}  {arrow} {change_str} ({pct_str})")

    def vix_emoji_text(self) -> str:
        arrow = "▲" if self.change >= 0 else "▼"
        sign = "+" if self.change >= 0 else ""
        pct_str = f"{sign}{self.change_pct:.2f}%"
        price_str = f"{self.price:,.2f}"
        change_str = f"{sign}{self.change:,.2f}"
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
        return (f"  {self.name:<16} {price_str:>12}  {arrow} {change_str} ({pct_str})   {label}")


# ─────────────────────────────────────────────────────────────────────────────
# Tencent Market Fetcher
# ─────────────────────────────────────────────────────────────────────────────

class TencentMarket:
    """
    Unified fetcher for all Tencent Finance qt.gtimg.cn quotes.
    Single request, multiple markets, GBK decode.

    前缀规则:
      (无)   = 完整版 10字段 [0~9]，含成交量/成交额
      s_     = 简版 5字段，解析快但字段少
      ff_    = 资金流向
      s_pk   = 盘口大单

    策略: 完整版优先；超时或全量失败时自动切换简版
    """

    SOURCE = "tencent"
    SOURCE_NAME = "腾讯财经"

    BASE_URL = "https://qt.gtimg.cn/q="

    # 完整版 codes（无 s_ 前缀）
    ALL_CODES = {
        # A股指数
        "sh000001": ("A股", "上证指数"),
        "sz399001": ("A股", "深证成指"),
        "sz399006": ("A股", "创业板指"),
        "sh000300": ("A股", "沪深300"),
        # 港股指数
        "hkHSI":    ("港股", "恒生指数"),
        "hkHSTECH": ("港股", "恒生科技"),
        "hkHSCEI":  ("港股", "国企指数"),
        # 美股指数
        "usDJI":    ("美股", "道琼斯"),
        "usINX":    ("美股", "标普500"),
        "usNDX":    ("美股", "纳斯达克100"),
        "usVIX":    ("美股", "VIX恐慌指数"),
        # 美股ETF
        "usSPY":    ("美股", "标普500ETF"),
        "usQQQ":    ("美股", "纳指100ETF"),
        "usIWM":    ("美股", "罗素2000ETF"),
        # 美股个股
        "usAAPL":   ("美股", "苹果"),
        "usTSLA":   ("美股", "特斯拉"),
        "usNVDA":   ("美股", "英伟达"),
        "usMSFT":   ("美股", "微软"),
        "usAMZN":   ("美股", "亚马逊"),
        "usGOOGL":  ("美股", "谷歌"),
        "usMETA":   ("美股", "Meta"),
        # 中概股
        "usJD":     ("美股", "京东"),
        "usBABA":   ("美股", "阿里巴巴"),
        "usPDD":    ("美股", "拼多多"),
        "usNTES":   ("美股", "网易"),
        "usBIDU":   ("美股", "百度"),
        # 港股个股
        "hk00700":  ("港股", "腾讯控股"),
        "hk09988":  ("港股", "阿里巴巴"),
        "hk03690":  ("港股", "美团"),
        "hk09888":  ("港股", "阿里云"),
        # A股个股
        "sh600519": ("A股", "贵州茅台"),
        "sz000858": ("A股", "五粮液"),
        "sh601318": ("A股", "中国平安"),
    }

    # 简版 codes（s_ 前缀）— 备用，字段少但解析快
    LITE_CODES = {
        "s_sh000001": ("A股", "上证指数"),
        "s_sz399001": ("A股", "深证成指"),
        "s_sz399006": ("A股", "创业板指"),
        "s_sh000300": ("A股", "沪深300"),
        "s_hkHSI":    ("港股", "恒生指数"),
        "s_hkHSTECH": ("港股", "恒生科技"),
        "s_hkHSCEI":  ("港股", "国企指数"),
        "s_usDJI":    ("美股", "道琼斯"),
        "s_usINX":    ("美股", "标普500"),
        "s_usNDX":    ("美股", "纳斯达克100"),
        "s_usVIX":    ("美股", "VIX恐慌指数"),
        "s_usSPY":    ("美股", "标普500ETF"),
        "s_usQQQ":    ("美股", "纳指100ETF"),
        "s_usIWM":    ("美股", "罗素2000ETF"),
        "s_usAAPL":   ("美股", "苹果"),
        "s_usTSLA":   ("美股", "特斯拉"),
        "s_usNVDA":   ("美股", "英伟达"),
        "s_usMSFT":   ("美股", "微软"),
        "s_usAMZN":   ("美股", "亚马逊"),
        "s_usGOOGL":  ("美股", "谷歌"),
        "s_usMETA":   ("美股", "Meta"),
        "s_usJD":     ("美股", "京东"),
        "s_usBABA":   ("美股", "阿里巴巴"),
        "s_usPDD":    ("美股", "拼多多"),
        "s_usNTES":   ("美股", "网易"),
        "s_usBIDU":   ("美股", "百度"),
        "s_hk00700":  ("港股", "腾讯控股"),
        "s_hk09988":  ("港股", "阿里巴巴"),
        "s_hk03690":  ("港股", "美团"),
        "s_hk09888":  ("港股", "阿里云"),
        "s_sh600519": ("A股", "贵州茅台"),
        "s_sz000858": ("A股", "五粮液"),
        "s_sh601318": ("A股", "中国平安"),
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.qq.com",
    }

    # ── US trading date ────────────────────────────────────────────────────────

    @staticmethod
    def _us_trading_date() -> str:
        """Compute current US trading day as YYYY-MM-DD.

        Beijing time (UTC+8):
          04:00-23:59 → today
          00:00-03:59 → previous calendar day
        Sat/Sun → roll back to preceding Fri.
        """
        beijing = datetime.now() + timedelta(hours=8)
        us_day = beijing.date()
        if beijing.hour < 4:
            us_day = (beijing - timedelta(days=1)).date()
        while us_day.isoweekday() >= 6:  # Sat=6, Sun=7
            us_day -= timedelta(days=1)
        return us_day.strftime("%Y-%m-%d")

    # ── Fetch ─────────────────────────────────────────────────────────────────

    @classmethod
    def _fetch_raw(cls, codes: list[str], lite: bool = False) -> list[dict]:
        """
        Fetch raw response from Tencent API.

        Args:
            codes:  list of API codes (with or without s_ prefix)
            lite:   if True, prepend "s_" to all codes
        Returns:
            list of {"code": str, "fields": list[str]}
        """
        if lite:
            api_codes = [f"s_{c}" if not c.startswith("s_") else c for c in codes]
        else:
            api_codes = codes

        url = cls.BASE_URL + ",".join(api_codes)
        try:
            r = requests.get(url, headers=cls.HEADERS, timeout=8)
            r.encoding = "gbk"
        except Exception as exc:
            logger.warning(f"[TencentMarket] 请求失败 (lite={lite}): {exc}")
            return []

        results = []
        code_set = set(api_codes)
        for line in r.text.strip().split(";"):
            if "=" not in line or "none_match" in line or '"' not in line:
                continue
            raw_code = line.split("=")[0].strip().replace("v_", "")
            if raw_code not in code_set:
                continue
            # Strip s_ prefix for canonical code
            canon = raw_code[2:] if raw_code.startswith("s_") else raw_code
            fields = line.split('"')[1].split("~")
            results.append({"code": canon, "fields": fields})

        return results

    @classmethod
    def _parse_full(cls, raw: dict) -> MarketQuote | None:
        """Parse full-version (no s_) raw response."""
        try:
            fields = raw["fields"]
            # 完整版: [3]=现价 [31]=涨跌额 [32]=涨跌幅 [6]=成交量 [7]=成交额
            price = float(fields[3])
            change = float(fields[31]) if len(fields) > 31 and fields[31] else 0.0
            change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0.0
            volume = int(float(fields[6])) if len(fields) > 6 and fields[6] else 0
            turnover = float(fields[7]) if len(fields) > 7 and fields[7] else 0
            return MarketQuote(
                name="", symbol=raw["code"], price=price, change=change,
                change_pct=change_pct, volume=volume, turnover=turnover,
            )
        except (IndexError, ValueError):
            return None

    @classmethod
    def _parse_lite(cls, raw: dict) -> MarketQuote | None:
        """Parse lite-version (s_ prefix) raw response."""
        try:
            fields = raw["fields"]
            # 简版: [3]=现价 [4]=涨跌额 [5]=涨跌幅 [6]=成交量 [7]=成交额
            price = float(fields[3])
            change = float(fields[4]) if len(fields) > 4 and fields[4] else 0.0
            change_pct = float(fields[5]) if len(fields) > 5 and fields[5] else 0.0
            volume = int(float(fields[6])) if len(fields) > 6 and fields[6] else 0
            turnover = float(fields[7]) if len(fields) > 7 and fields[7] else 0
            return MarketQuote(
                name="", symbol=raw["code"], price=price, change=change,
                change_pct=change_pct, volume=volume, turnover=turnover,
            )
        except (IndexError, ValueError):
            return None

    @classmethod
    def fetch_all(cls, codes: list[str] = None) -> list[MarketQuote]:
        """
        Fetch quotes with fallback: full version → lite version on failure.

        策略:
          1. 完整版（无 s_ 前缀），timeout=8s
          2. 若成功获取 >=50% 数据 → 返回完整版（含成交量/成交额）
          3. 若超时或成功数 <50% → 切换简版（s_ 前缀），timeout=5s
          4. 若简版也失败 → 返回空列表
        """
        if codes is None:
            codes = list(cls.ALL_CODES.keys())

        trading_date = cls._us_trading_date()

        # ── Step 1: 完整版 ────────────────────────────────────────────────
        raw_list = cls._fetch_raw(codes, lite=False)
        quotes: list[MarketQuote] = []
        for raw in raw_list:
            q = cls._parse_full(raw)
            if q:
                q.market, q.name = cls.ALL_CODES.get(raw["code"], ("其他", raw["code"]))
                q.source = cls.SOURCE
                q.trading_date = trading_date
                quotes.append(q)

        total = len(codes)
        success_pct = len(quotes) / total if total else 0

        # ── Step 2: 完整版成功 >= 50% → 直接返回 ─────────────────────────
        if success_pct >= 0.5:
            code_order = {c: i for i, c in enumerate(codes)}
            quotes.sort(key=lambda q: code_order.get(q.symbol, 999))
            logger.info(f"[TencentMarket] 完整版成功 {len(quotes)}/{total} ({success_pct:.0%})")
            return quotes

        # ── Step 3: 完整版失败 → 切换简版 ─────────────────────────────────
        logger.warning(
            f"[TencentMarket] 完整版成功率 {len(quotes)}/{total} ({success_pct:.0%}) "
            "→ 切换简版"
        )
        raw_list_lite = cls._fetch_raw(codes, lite=True)
        quotes_lite: list[MarketQuote] = []
        for raw in raw_list_lite:
            q = cls._parse_lite(raw)
            if q:
                # Lite code map: strip s_ prefix to look up in ALL_CODES
                canon = raw["code"][2:] if raw["code"].startswith("s_") else raw["code"]
                q.market, q.name = cls.ALL_CODES.get(canon, ("其他", canon))
                q.source = cls.SOURCE
                q.trading_date = trading_date
                quotes_lite.append(q)

        if len(quotes_lite) >= len(quotes):
            code_order = {c: i for i, c in enumerate(codes)}
            quotes_lite.sort(key=lambda q: code_order.get(q.symbol, 999))
            logger.warning(f"[TencentMarket] 简版成功 {len(quotes_lite)}/{total}")
            return quotes_lite

        # 简版也没有更好 → 保留完整版结果
        code_order = {c: i for i, c in enumerate(codes)}
        quotes.sort(key=lambda q: code_order.get(q.symbol, 999))
        return quotes

    # ── Format ────────────────────────────────────────────────────────────────

    @classmethod
    def format_global_report(cls, quotes: list[MarketQuote] = None,
                             markets: list[str] = None) -> str:
        """
        Format quotes as emoji pure-text global market report.

        Args:
            quotes:   fetched quotes (auto-fetched if None)
            markets:  list of markets to include, default ["A股", "港股", "美股"]
        """
        if quotes is None:
            quotes = cls.fetch_all()
        if not quotes:
            return "🌏 全球市场总览\n\n⚠️ 暂时无法获取数据，请稍后重试\n"

        if markets is None:
            markets = ["A股", "港股", "美股"]

        trading_date = quotes[0].trading_date if quotes else "—"

        lines = [
            f"🌏 全球市场总览  {trading_date}",
            "",
        ]

        for market in markets:
            market_quotes = [q for q in quotes if q.market == market]
            if not market_quotes:
                continue

            if market == "A股":
                lines.append("📈 A股大盘")
            elif market == "港股":
                lines.append("📈 港股")
            elif market == "美股":
                lines.append("📈 美股夜盘")

            for q in market_quotes:
                if q.symbol == "usVIX":
                    lines.append("")
                    lines.append("─" * 50)
                    lines.append(q.vix_emoji_text())
                else:
                    lines.append(q.emoji_text() + "  🌐")

            lines.append("")

        lines.append("  ⚠️ 数据仅供参考，非实时交易价格")

        return "\n".join(lines)

    @classmethod
    def format_us_report(cls, quotes: list[MarketQuote] = None) -> str:
        """US market only — indices + VIX (alias for backwards compat)."""
        if quotes is None:
            quotes = cls.fetch_all(codes=["usDJI","usINX","usNDX","usVIX"])
        us_quotes = [q for q in quotes if q.market == "美股"]
        return cls.format_global_report(quotes=us_quotes, markets=["美股"])


# ─────────────────────────────────────────────────────────────────────────────
# Fund Flow (资金流向) — ff_ 前缀
# ⚠️ 注：ff_ 接口对个股（如 sh600519）返回 none_match，
#    可能是该接口仅支持部分指数或需要特殊代码格式，暂作保留功能。
# ─────────────────────────────────────────────────────────────────────────────

class FundFlow:
    """
    主力资金流向 via ff_ 前缀 qt.gtimg.cn

    ⚠️ 注意：经验证，ff_ 前缀对 A股个股（如 sh600519）返回 none_match，
    该接口可能仅支持部分指数基金，或需要其他代码格式。
    如需资金流向数据，建议使用东方财富等专项 API。

    Usage:
        from market_quotes import FundFlow
        result = FundFlow.fetch("sh600519")   # 茅台（当前返回 none_match）
        print(result)
    """

    BASE_URL = "https://qt.gtimg.cn/q="

    @classmethod
    def fetch(cls, code: str) -> dict:
        """Fetch fund flow data for a single code.

        Args:
            code: Tencent code without prefix, e.g. "sh600519" or "usAAPL"
        Returns:
            dict with keys: name, code, time, main_net, main_net_rate,
                            huge_net, huge_net_rate,
                            big_net, big_net_rate,
                            mid_net, small_net
        """
        url = f"{cls.BASE_URL}ff_{code}"
        try:
            r = requests.get(url, headers=cls.HEADERS, timeout=10)
            r.encoding = "gbk"
        except Exception as exc:
            logger.warning(f"[FundFlow] 请求失败: {exc}")
            return {}

        line = r.text.strip()
        if "=" not in line or "none_match" in line:
            return {}

        raw = line.split('"')[1] if '"' in line else ""
        if not raw:
            return {}

        fields = raw.split("~")
        try:
            return {
                "code": code,
                "time": fields[0] if len(fields) > 0 else "",
                "main_net": float(fields[1]) if len(fields) > 1 and fields[1] else 0,
                "main_net_rate": float(fields[2]) if len(fields) > 2 and fields[2] else 0,
                "huge_net": float(fields[3]) if len(fields) > 3 and fields[3] else 0,
                "huge_net_rate": float(fields[4]) if len(fields) > 4 and fields[4] else 0,
                "big_net": float(fields[5]) if len(fields) > 5 and fields[5] else 0,
                "big_net_rate": float(fields[6]) if len(fields) > 6 and fields[6] else 0,
                "mid_net": float(fields[7]) if len(fields) > 7 and fields[7] else 0,
                "small_net": float(fields[8]) if len(fields) > 8 and fields[8] else 0,
            }
        except (IndexError, ValueError) as exc:
            logger.warning(f"[FundFlow] 解析失败 {code}: {exc}")
            return {}

    @classmethod
    def format_report(cls, code: str) -> str:
        """Format fund flow as emoji text report."""
        data = cls.fetch(code)
        if not data:
            return f"⚠️ 资金流向查询失败: {code}（该接口可能不支持此标的）"

        lines = [
            f"💰 资金流向  {data.get('code', code)}",
            "",
            f"  主力净流入   {data.get('main_net'):>15,.0f} 元  ({data.get('main_net_rate', 0):+.2f}%)",
            f"  超大单净流入 {data.get('huge_net'):>15,.0f} 元  ({data.get('huge_net_rate', 0):+.2f}%)",
            f"  大单净流入   {data.get('big_net'):>15,.0f} 元  ({data.get('big_net_rate', 0):+.2f}%)",
            f"  中单净流入   {data.get('mid_net'):>15,.0f} 元",
            f"  小单净流入   {data.get('small_net'):>15,.0f} 元",
            "",
            "  ⚠️ 数据仅供参考，非实时交易价格",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Order Book / Block Trade (盘口大单) — s_pk 前缀
# ─────────────────────────────────────────────────────────────────────────────

class BlockTrade:
    """
    盘口大单分析 via s_pk 前缀 qt.gtimg.cn

    Usage:
        from market_quotes import BlockTrade
        result = BlockTrade.fetch("sh600519")   # 茅台
        print(result)

    返回字段:
        [0]=买盘大单比例 [1]=买盘小单比例 [2]=卖盘大单比例 [3]=卖盘小单比例
        注意: 接口返回原始比例值(如 15.23 表示 15.23%)
    """

    BASE_URL = "https://qt.gtimg.cn/q="

    @classmethod
    def fetch(cls, code: str) -> dict:
        """Fetch block trade data for a single code."""
        url = f"{cls.BASE_URL}s_pk{code}"
        try:
            r = requests.get(url, timeout=10)
            r.encoding = "gbk"
        except Exception as exc:
            logger.warning(f"[BlockTrade] 请求失败: {exc}")
            return {}

        line = r.text.strip()
        if "=" not in line or "none_match" in line:
            return {}

        raw = line.split('"')[1] if '"' in line else ""
        if not raw:
            return {}

        fields = raw.split("~")
        try:
            return {
                "code": code,
                "buy_big": float(fields[0]) if len(fields) > 0 and fields[0] else 0,
                "buy_small": float(fields[1]) if len(fields) > 1 and fields[1] else 0,
                "sell_big": float(fields[2]) if len(fields) > 2 and fields[2] else 0,
                "sell_small": float(fields[3]) if len(fields) > 3 and fields[3] else 0,
            }
        except (IndexError, ValueError) as exc:
            logger.warning(f"[BlockTrade] 解析失败 {code}: {exc}")
            return {}

    @classmethod
    def format_report(cls, code: str) -> str:
        """Format block trade as emoji text report."""
        data = cls.fetch(code)
        if not data:
            return f"⚠️ 盘口大单查询失败: {code}"

        lines = [
            f"📊 盘口大单  {data.get('code', code)}",
            "",
            f"  买盘大单比例  {data.get('buy_big', 0):.2f}%",
            f"  买盘小单比例  {data.get('buy_small', 0):.2f}%",
            f"  卖盘大单比例  {data.get('sell_big', 0):.2f}%",
            f"  卖盘小单比例  {data.get('sell_small', 0):.2f}%",
            "",
            "  📌 大单占比高 = 主力活跃；小单占比高 = 散户活跃",
            "  ⚠️ 数据仅供参考，非实时交易价格",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrappers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_global_market() -> list[MarketQuote]:
    """Fetch all market quotes (A股 + 港股 + 美股)."""
    return TencentMarket.fetch_all()


def format_global_report() -> str:
    """Format full global market report as emoji text."""
    return TencentMarket.format_global_report()

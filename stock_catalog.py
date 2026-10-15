"""Immediate local company-name suggestions, with optional Yahoo lookup."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import krx_catalog


@dataclass(frozen=True, slots=True)
class Stock:
    symbol: str
    name: str
    market: str
    currency: str


# Editorial priority, not a live market-cap ranking. No network is needed to type.
PRIORITY: Final = (
    Stock("005930.KS", "삼성전자", "한국 · 코스피", "KRW"),
    Stock("000660.KS", "SK하이닉스", "한국 · 코스피", "KRW"),
    Stock("207940.KS", "삼성바이오로직스", "한국 · 코스피", "KRW"),
    Stock("005935.KS", "삼성전자우", "한국 · 코스피 · 우선주", "KRW"),
    Stock("006400.KS", "삼성SDI", "한국 · 코스피", "KRW"),
    Stock("028260.KS", "삼성물산", "한국 · 코스피", "KRW"),
    Stock("032830.KS", "삼성생명", "한국 · 코스피", "KRW"),
    Stock("009150.KS", "삼성전기", "한국 · 코스피", "KRW"),
    Stock("010140.KS", "삼성중공업", "한국 · 코스피", "KRW"),
    Stock("018260.KS", "삼성에스디에스", "한국 · 코스피", "KRW"),
    Stock("005380.KS", "현대차", "한국 · 코스피", "KRW"),
    Stock("000270.KS", "기아", "한국 · 코스피", "KRW"),
    Stock("373220.KS", "LG에너지솔루션", "한국 · 코스피", "KRW"),
    Stock("051910.KS", "LG화학", "한국 · 코스피", "KRW"),
    Stock("035420.KS", "네이버", "한국 · 코스피", "KRW"),
    Stock("035720.KS", "카카오", "한국 · 코스피", "KRW"),
    Stock("068270.KS", "셀트리온", "한국 · 코스피", "KRW"),
    Stock("005490.KS", "POSCO홀딩스", "한국 · 코스피", "KRW"),
    Stock("105560.KS", "KB금융", "한국 · 코스피", "KRW"),
    Stock("055550.KS", "신한지주", "한국 · 코스피", "KRW"),
    Stock("012450.KS", "한화에어로스페이스", "한국 · 코스피", "KRW"),
    Stock("042700.KS", "한미반도체", "한국 · 코스피", "KRW"),
    Stock("086520.KQ", "에코프로", "한국 · 코스닥", "KRW"),
    Stock("247540.KQ", "에코프로비엠", "한국 · 코스닥", "KRW"),
    Stock("196170.KQ", "알테오젠", "한국 · 코스닥", "KRW"),
    Stock("NVDA", "엔비디아", "미국 · 나스닥", "USD"),
    Stock("AAPL", "애플", "미국 · 나스닥", "USD"),
    Stock("MSFT", "마이크로소프트", "미국 · 나스닥", "USD"),
    Stock("TSLA", "테슬라", "미국 · 나스닥", "USD"),
    Stock("AMZN", "아마존", "미국 · 나스닥", "USD"),
    Stock("GOOGL", "알파벳 A (구글)", "미국 · 나스닥", "USD"),
    Stock("GOOG", "알파벳 C (구글)", "미국 · 나스닥", "USD"),
    Stock("META", "메타", "미국 · 나스닥", "USD"),
    Stock("AVGO", "브로드컴", "미국 · 나스닥", "USD"),
    Stock("AMD", "AMD", "미국 · 나스닥", "USD"),
    Stock("MU", "마이크론", "미국 · 나스닥", "USD"),
    Stock("INTC", "인텔", "미국 · 나스닥", "USD"),
    Stock("TSM", "TSMC ADR", "미국 · NYSE · ADR", "USD"),
    Stock("SPY", "S&P 500 ETF", "미국 · NYSE Arca · ETF", "USD"),
    Stock("QQQ", "나스닥 100 ETF", "미국 · 나스닥 · ETF", "USD"),
)
ALIASES: Final = {
    "000660.KS": ("하이닉스", "에스케이하이닉스", "sk hynix"),
    "005930.KS": ("samsung", "samsung electronics"),
    "005380.KS": ("현대자동차", "hyundai"),
    "035420.KS": ("naver", "네이버"), "005490.KS": ("포스코",),
    "NVDA": ("nvidia",), "AAPL": ("apple",),
    "MSFT": ("microsoft", "마소"), "TSLA": ("tesla",),
    "AMZN": ("amazon",), "GOOGL": ("구글", "google", "alphabet"),
    "GOOG": ("구글", "google",), "META": ("페이스북", "facebook"),
    "AMD": ("에이엠디",), "MU": ("micron",),
    "TSM": ("대만반도체", "티에스엠씨"),
}


def _build_catalog(listings: tuple[krx_catalog.Listing, ...]) -> tuple[Stock, ...]:
    priorities = {stock.symbol: index for index, stock in enumerate(PRIORITY)}
    ordered = sorted(listings, key=lambda item: (
        priorities.get(f"{item.code}.{item.market}", len(PRIORITY)), -item.cap, item.code))
    domestic = tuple(Stock(f"{item.code}.{item.market}", item.name,
                          "한국 · " + {"KS": "코스피", "KQ": "코스닥"}[item.market]
                          + (f" · {item.kind}" if item.kind else ""), "KRW") for item in ordered)
    return domestic + tuple(stock for stock in PRIORITY if stock.currency != "KRW")


def _index(stocks: tuple[Stock, ...]) -> tuple[tuple[Stock, tuple[str, ...]], ...]:
    return tuple((stock, tuple(name.casefold().replace(" ", "") for name in
                              (stock.name, stock.symbol, stock.symbol.split(".")[0],
                               *ALIASES.get(stock.symbol, ())))) for stock in stocks)


CATALOG: Final = _build_catalog(krx_catalog.load_catalog())
_search_index = _index(CATALOG)


def catalog() -> tuple[Stock, ...]:
    """Return the latest complete in-memory catalog, without disk or network I/O."""
    return tuple(stock for stock, _ in _search_index)


def refresh_catalog() -> bool:
    """Worker-only daily refresh; publish a fully built index in one assignment."""
    global _search_index
    fresh = krx_catalog.refresh_catalog()
    if fresh is None:
        return False
    _search_index = _index(_build_catalog(fresh))
    return True


def search(query: str, preferred: Iterable[str] = ()) -> list[Stock]:
    """Return five stable suggestions from pre-normalized local names."""
    term = query.strip().casefold().replace(" ", "")
    preferred_symbols = set(preferred)
    ranked: list[tuple[int, int, int, Stock]] = []
    for index, (stock, keys) in enumerate(_search_index):
        if term and not any(term in key for key in keys):
            continue
        match_rank = 0 if term in keys else 1 if any(key.startswith(term) for key in keys) else 2
        ranked.append((match_rank, int(stock.symbol not in preferred_symbols), index, stock))
    ranked.sort(key=lambda row: row[:3])
    return [row[3] for row in ranked[:5]]


def search_remote(query: str) -> list[Stock]:
    """Blocking fallback; call only on a worker, never on the Tk thread."""
    params = urlencode({"q": query.strip(), "quotesCount": 5, "newsCount": 0})
    request = Request("https://query1.finance.yahoo.com/v1/finance/search?" + params,
                      headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=5) as response:
        payload = json.load(response)
    results: list[Stock] = []
    for item in payload.get("quotes", []):
        symbol = item.get("symbol")
        name = item.get("shortname") or item.get("longname")
        if not isinstance(symbol, str) or not isinstance(name, str):
            continue
        known = next((stock for stock in catalog() if stock.symbol == symbol), None)
        if known is not None:
            results.append(known)
            continue
        exchange = item.get("exchDisp") or item.get("exchange") or "시장 확인 필요"
        kind = item.get("quoteType", "")
        currency = item.get("currency", "")
        if symbol.endswith((".KS", ".KQ")):
            currency = "KRW"
        results.append(Stock(symbol, name, f"{exchange} · {kind}", str(currency)))
    return results[:5]

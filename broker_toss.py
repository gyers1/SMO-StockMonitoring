from __future__ import annotations

import math
import time
from datetime import datetime
from decimal import Decimal
from threading import Lock
from typing import ClassVar, final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from broker_transport import BrokerTransport
from broker_types import BrokerError, Quote


class TossPrice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    symbol: str
    lastPrice: str
    currency: str
    timestamp: datetime | None = None


class TossPrices(BaseModel):
    result: list[TossPrice]


class RankingPrice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, allow_inf_nan=False)
    lastPrice: Decimal = Field(gt=0)
    basePrice: Decimal = Field(gt=0)
    changeRate: Decimal | None = None


class RankingItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    symbol: str
    currency: str
    price: RankingPrice


class Rankings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    rankedAt: datetime | None = None
    rankings: tuple[RankingItem, ...]


class RankingResponse(BaseModel):
    result: Rankings


def timestamp(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        raise BrokerError('증권사 시세 시각의 시간대가 누락되었습니다.')
    stamp = int(value.timestamp())
    if stamp <= 0 or stamp > time.time() + 300:
        raise BrokerError('증권사 시세 시각이 유효하지 않습니다.')
    return stamp


@final
class TossQuotes:
    """Share each market ranking snapshot for five seconds across quote workers."""

    def __init__(self, wire: BrokerTransport) -> None:
        self._wire = wire
        self._lock = Lock()
        self._rankings: dict[str, tuple[float, Rankings | None]] = {}

    def _ranking(self, market: str, token: str) -> Rankings | None:
        with self._lock:
            cached = self._rankings.get(market)
            if cached is not None and time.monotonic() - cached[0] < 5:
                return cached[1]
            try:
                raw = self._wire.request('https://openapi.tossinvest.com/api/v1/rankings',
                    fields={'type': 'MARKET_TRADING_AMOUNT', 'marketCountry': market,
                            'duration': 'realtime', 'count': '100'}, token=token, get=True)
                result = RankingResponse.model_validate_json(raw).result
                if not timestamp(result.rankedAt):
                    result = None
            except (BrokerError, ValidationError, ValueError, OverflowError):
                # Rankings are optional coverage; /prices remains independently usable.
                result = None
            self._rankings[market] = (time.monotonic(), result)
            return result

    def fetch(self, symbol: str, code: str, domestic: bool, token: str) -> Quote:
        currency = 'KRW' if domestic else 'USD'
        exchange = '국내 통합(KRX·NXT)' if domestic else '미국'
        ranking = self._ranking('KR' if domestic else 'US', token)
        ranked_quote: Quote | None = None
        ranked_price: Decimal | None = None
        if ranking is not None:
            ranked_matches = [row for row in ranking.rankings if row.symbol == code]
            if len(ranked_matches) == 1:
                row = ranked_matches[0]
                if row.currency == currency and row.price.changeRate is not None:
                    price, change = float(row.price.lastPrice), float(row.price.changeRate * 100)
                    if math.isfinite(price) and math.isfinite(change):
                        ranked_price = row.price.lastPrice
                        ranked_quote = Quote(price, change, currency, timestamp(ranking.rankedAt), symbol,
                            '토스증권', exchange, fetched_at=int(time.time()),
                            session='증권사 랭킹 집계 시세',
                            change_note='전일 대비 · 시장 거래대금 상위 100종목 랭킹 제공값')
                        if time.time() - ranked_quote.timestamp <= 60:
                            return ranked_quote
        payload = TossPrices.model_validate_json(self._wire.request(
            'https://openapi.tossinvest.com/api/v1/prices', fields={'symbols': code}, token=token, get=True))
        matches = [item for item in payload.result if item.symbol == code]
        if len(matches) != 1 or matches[0].currency != currency:
            raise BrokerError('종목 또는 통화가 일치하지 않아 시세를 표시하지 않습니다.')
        item = matches[0]
        price = float(item.lastPrice.replace(',', '').strip())
        if not math.isfinite(price):
            raise BrokerError('증권사 시세 값이 유효하지 않습니다.')
        stamp = timestamp(item.timestamp)
        # After close, keep an old ranking only when /prices confirms its exact price
        # and latest trade has not advanced past the original ranking timestamp.
        if (ranked_quote is not None and ranking is not None and ranking.rankedAt is not None
                and item.timestamp is not None and stamp > 0
                and item.timestamp <= ranking.rankedAt
                and Decimal(item.lastPrice.replace(',', '').strip()) == ranked_price):
            return ranked_quote
        return Quote(price, None, currency, stamp, symbol,
            '토스증권', exchange, fetched_at=int(time.time()),
            change_note='등락률 미제공 · 최근 랭킹 미포함 또는 기준값 미제공, 현재가 API에 전일 기준가가 없습니다.')



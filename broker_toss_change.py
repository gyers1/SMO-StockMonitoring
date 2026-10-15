from __future__ import annotations

import math
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from broker_transport import BrokerTransport
from broker_types import BrokerError, Quote


class Candle(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    timestamp: datetime
    closePrice: str
    currency: str


class CandlePage(BaseModel):
    candles: list[Candle]


class CandleResponse(BaseModel):
    result: CandlePage


def previous_close_change(wire: BrokerTransport, token: str, quote: Quote) -> float | None:
    """Compare with the preceding exchange-local daily adjusted close."""
    if not quote.timestamp:
        return None
    code = quote.symbol[:-3] if quote.symbol.endswith(('.KS', '.KQ')) else quote.symbol
    try:
        response = CandleResponse.model_validate_json(wire.request(
            'https://openapi.tossinvest.com/api/v1/candles', token=token, get=True,
            fields={'symbol': code, 'interval': '1d', 'count': '3', 'adjusted': 'true'}))
        candidates = []
        for candle in response.result.candles:
            zone = candle.timestamp.tzinfo
            if zone is None or candle.currency != quote.currency:
                return None
            quote_date = datetime.fromtimestamp(quote.timestamp, zone).date()
            if candle.timestamp.date() < quote_date:
                candidates.append(candle)
        if not candidates:
            return None
        base = float(max(candidates, key=lambda candle: candle.timestamp).closePrice)
        if not math.isfinite(base) or base <= 0:
            return None
        change = (quote.price - base) / base * 100
        return change if math.isfinite(change) else None
    except (BrokerError, ValidationError, ValueError, OverflowError):
        # Missing reference data must not discard a valid current price.
        return None

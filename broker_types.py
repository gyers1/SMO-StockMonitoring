from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, override

KST: Final = timezone(timedelta(hours=9))


@dataclass(frozen=True, slots=True)
class BrokerError(Exception):
    message: str
    code: int = 0
    @override
    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class Quote:
    price: float
    change_pct: float | None
    currency: str
    timestamp: int
    symbol: str = ''
    source: str = ''
    exchange: str = ''
    delay_minutes: int | None = None
    fetched_at: int = 0
    session: str = '증권사 제공 시세'

    @property
    def status_text(self) -> str:
        return f'{self.session} · 5초 조회'

    @property
    def tooltip(self) -> str:
        observed = datetime.fromtimestamp(self.timestamp, KST).strftime('%Y-%m-%d %H:%M:%S KST') if self.timestamp else '체결시각 미제공'
        received = datetime.fromtimestamp(self.fetched_at, KST).strftime('%Y-%m-%d %H:%M:%S KST') if self.fetched_at else '미수신'
        return (f'{self.symbol} · {self.exchange} · {self.currency}\n출처: {self.source}\n'
                f'시세 시각: {observed}\n수신 시각: {received}\n5초 간격 REST 조회 · 종목 수와 호출 제한에 따라 지연될 수 있습니다.\n'
                '실시간 시세 권한과 제공 범위는 증권사 이용 조건에 따릅니다.')

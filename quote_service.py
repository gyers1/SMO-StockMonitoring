from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from dataclasses import dataclass
from typing import final

from broker_adapter import BrokerAdapter
from broker_types import BrokerError, Quote

__all__ = ['Quote', 'QuoteService', 'test_connection']


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    success: bool
    message: str


def check_connection(provider: str, key: str, secret: str) -> ConnectionResult:
    try:
        adapter = BrokerAdapter(provider, key, secret)
        _ = adapter.fetch('005930.KS')
    except BrokerError as exc:
        return ConnectionResult(False, str(exc))
    return ConnectionResult(True, f'{adapter.name} 연결 확인 · 국내 시세 조회 성공 (미국 시세 권한은 별도 확인)')


def test_connection(provider: str, key: str, secret: str) -> str:
    return check_connection(provider, key, secret).message


@final
class QuoteService:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='broker-quotes')
        self._lock = Lock()
        self._quotes: dict[str, Quote] = {}
        self._attempts: dict[str, float] = {}
        self._pending: set[str] = set()
        self._errors: dict[str, str] = {}
        self._closed = False
        self._generation = 0
        self._adapter: BrokerAdapter | None = None
        self._status = '설정에서 증권사 API를 연결하세요.'

    @property
    def configured(self) -> bool:
        with self._lock:
            return self._adapter is not None

    @property
    def status_text(self) -> str:
        with self._lock:
            return self._status

    def configure(self, provider: str, key: str, secret: str) -> None:
        adapter = None
        try:
            adapter = BrokerAdapter(provider, key, secret)
            status = f'{adapter.name} · 시세 연결 대기'
        except BrokerError as exc:
            status = str(exc)
        with self._lock:
            self._generation += 1
            self._adapter = adapter
            self._status = status
            self._quotes.clear()
            self._attempts.clear()
            self._pending.clear()
            self._errors.clear()

    def request(self, symbol: str) -> None:
        with self._lock:
            if self._closed or self._adapter is None or symbol in self._pending or len(self._pending) >= 24:
                return
            interval = 30 if symbol in self._errors else 5
            if time.monotonic() - self._attempts.get(symbol, -math.inf) < interval:
                return
            self._pending.add(symbol)
            self._attempts[symbol] = time.monotonic()
            _ = self._pool.submit(self._load, symbol, self._adapter, self._generation)

    def _load(self, symbol: str, adapter: BrokerAdapter, generation: int) -> None:
        with self._lock:
            if generation != self._generation or self._closed:
                return
        result = None
        error = ''
        try:
            result = adapter.fetch(symbol)
        except BrokerError as exc:
            error = str(exc)
        with self._lock:
            if generation != self._generation or self._closed:
                return
            self._pending.discard(symbol)
            if result is not None:
                current = self._quotes.get(symbol)
                if current and current.timestamp and result.timestamp and result.timestamp < current.timestamp:
                    error = '이전 시세가 수신되어 마지막 확인 가격을 유지합니다.'
                else:
                    self._quotes[symbol] = result
                    _ = self._errors.pop(symbol, None)
                    self._status = f'{adapter.name} · 5초 자동 조회'
            if error:
                self._errors[symbol] = error
                self._status = f'{adapter.name} · 일부 시세 확인 필요'

    def get(self, symbol: str) -> Quote | None:
        with self._lock:
            return self._quotes.get(symbol)

    def error(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._errors

    def message(self, symbol: str) -> str:
        with self._lock:
            return self._errors.get(symbol, self._status)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._generation += 1
        self._pool.shutdown(wait=False, cancel_futures=True)

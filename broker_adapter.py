from __future__ import annotations

import math
import re
import time
from datetime import datetime
from threading import Lock
from typing import ClassVar, final

from pydantic import BaseModel, ConfigDict, ValidationError
from broker_transport import BrokerTransport
from broker_types import BrokerError, KST, Quote
from broker_kis import kis_client


class Token(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    access_token: str = ''
    token: str = ''
    expires_in: int = 0
    expires_dt: str = ''
    return_code: int = 0


class TossPrice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    symbol: str
    lastPrice: str
    currency: str
    timestamp: datetime | None = None


class TossPrices(BaseModel):
    result: list[TossPrice]


class KiwoomPrice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    return_code: int
    return_msg: str = ''
    stk_cd: str = ''
    cur_prc: str = ''
    flu_rt: str = ''
    stex_tp: str = ''
    curr_unit: str = ''


def decimal(value: str, *, absolute: bool = False) -> float:
    number = float(value.replace(',', '').strip())
    if not math.isfinite(number):
        raise BrokerError('증권사 시세 값이 유효하지 않습니다.')
    return abs(number) if absolute else number


@final
class BrokerAdapter:
    def __init__(self, provider: str, key: str, secret: str) -> None:
        if provider == 'mirae':
            raise BrokerError('미래에셋 공개 키 방식 시세 API 미지원 · 다른 증권사를 선택하세요.')
        if provider not in ('toss', 'kiwoom', 'kis'):
            raise BrokerError('설정에서 증권사 API를 연결하세요.')
        if not key.strip() or not secret.strip():
            raise BrokerError('API 키와 Secret을 모두 입력하세요.')
        self.provider = provider
        self._key, self._secret = key.strip(), secret.strip()
        self._token = ''
        self._expires = 0.0
        self._auth_lock = Lock()
        self._wire = BrokerTransport()
        self._markets: dict[str, str] = {}
        self._kis = kis_client(self._key, self._secret) if provider == 'kis' else None

    @property
    def name(self) -> str:
        return {'toss': '토스증권', 'kiwoom': '키움증권', 'kis': '한국투자증권'}[self.provider]

    def _authorize(self) -> str:
        with self._auth_lock:
            if self._token and time.time() < self._expires - 60:
                return self._token
            if self.provider == 'toss':
                body = self._wire.request('https://openapi.tossinvest.com/oauth2/token', form=True,
                    fields={'grant_type': 'client_credentials', 'client_id': self._key, 'client_secret': self._secret})
                parsed = Token.model_validate_json(body)
                token, expires = parsed.access_token, time.time() + parsed.expires_in
            else:
                body = self._wire.request('https://api.kiwoom.com/oauth2/token', api_id='au10001',
                    fields={'grant_type': 'client_credentials', 'appkey': self._key, 'secretkey': self._secret})
                parsed = Token.model_validate_json(body)
                if parsed.return_code:
                    raise BrokerError('인증 실패 · API 키, 등록 IP와 서비스 신청을 확인하세요.')
                token = parsed.token
                expires = datetime.strptime(parsed.expires_dt, '%Y%m%d%H%M%S').replace(tzinfo=KST).timestamp()
            if not token or expires <= time.time() + 60:
                raise BrokerError('증권사 인증 토큰이 유효하지 않습니다. 키를 다시 확인하세요.')
            self._token, self._expires = token, expires
            return token

    def fetch(self, symbol: str) -> Quote:
        domestic = symbol.endswith(('.KS', '.KQ'))
        code = symbol[:-3] if domestic else symbol
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9.-]{0,19}', code) or (not domestic and (code.isdigit() or re.search(r'\.(?:T|L|HK|TO|V|AX|F|DE)$', code))):
            raise BrokerError('이 연결은 국내·미국 종목만 지원합니다.')
        try:
            if self._kis is not None:
                return self._kis.fetch(symbol)
            token = self._authorize()
            if self.provider == 'toss':
                payload = TossPrices.model_validate_json(self._wire.request(
                    'https://openapi.tossinvest.com/api/v1/prices', fields={'symbols': code}, token=token, get=True))
                matches = [p for p in payload.result if p.symbol == code]
                if len(matches) != 1 or matches[0].currency != ('KRW' if domestic else 'USD'):
                    raise BrokerError('종목 또는 통화가 일치하지 않아 시세를 표시하지 않습니다.')
                item = matches[0]
                price = decimal(item.lastPrice)
                stamp = 0
                if item.timestamp is not None:
                    if item.timestamp.tzinfo is None:
                        raise BrokerError('증권사 시세 시각의 시간대가 누락되었습니다.')
                    stamp = int(item.timestamp.timestamp())
                    if stamp <= 0 or stamp > time.time() + 300:
                        raise BrokerError('증권사 시세 시각이 유효하지 않습니다.')
                result = Quote(price, None, item.currency, stamp, symbol, self.name,
                    '국내 통합(KRX·NXT)' if domestic else '미국', fetched_at=int(time.time()),
                    change_note='등락률 미제공 · 현재가 API에 전일 기준가가 없습니다.')
            else:
                result = self._kiwoom(symbol, code, domestic, token)
            if result.price <= 0:
                raise BrokerError('현재가 미제공 · 거래 상태 또는 시세 권한을 확인하세요.')
            return result
        except BrokerError as exc:
            if exc.code in (401, 403, 8003, 8005, 8010, 8103):
                with self._auth_lock:
                    self._token, self._expires = '', 0.0
            raise
        except (ValidationError, ValueError, OverflowError):
            raise BrokerError('증권사 응답 형식이 올바르지 않아 시세를 표시하지 않습니다.') from None

    def _kiwoom(self, symbol: str, code: str, domestic: bool, token: str) -> Quote:
        if domestic:
            raw = self._wire.request('https://api.kiwoom.com/api/dostk/stkinfo',
                fields={'stk_cd': code}, token=token, api_id='ka10001')
            item = KiwoomPrice.model_validate_json(raw)
            if item.return_code:
                raise BrokerError('키움 시세 조회 거절 · 등록 IP와 시세 권한을 확인하세요.', item.return_code)
            if item.stk_cd != code:
                raise BrokerError('응답 종목이 달라 시세를 표시하지 않습니다.')
            exchange, currency = 'KRX', 'KRW'
        else:
            markets = (self._markets[code],) if code in self._markets else ('ND', 'NY', 'NA')
            item = None
            for market in markets:
                raw = self._wire.request('https://api.kiwoom.com/api/us/mrkcond',
                    fields={'stk_cd': code, 'stex_tp': market}, token=token, api_id='usa20100')
                candidate = KiwoomPrice.model_validate_json(raw)
                missing = candidate.return_code in (1901, 1902, 1903) or (
                    candidate.return_code == 7 and re.search(r'\[190[123]:', candidate.return_msg) is not None)
                if candidate.return_code != 0 and not missing:
                    raise BrokerError('키움 미국 시세 조회 거절 · 등록 IP와 미국 시세 권한을 확인하세요.', candidate.return_code)
                if candidate.return_code == 0 and candidate.stk_cd == code and candidate.stex_tp == market and candidate.curr_unit == 'USD' and candidate.cur_prc and decimal(candidate.cur_prc, absolute=True) > 0:
                    item = candidate
                    self._markets[code] = market
                    break
            if item is None:
                raise BrokerError('미국 시세 미제공 · 종목과 미국 시세 이용 권한을 확인하세요.')
            exchange, currency = {'ND': 'NASDAQ', 'NY': 'NYSE', 'NA': 'AMEX'}[item.stex_tp], 'USD'
        change = decimal(item.flu_rt) if item.flu_rt.strip() else None
        return Quote(decimal(item.cur_prc, absolute=True), change, currency, 0,
            symbol, self.name, exchange, fetched_at=int(time.time()))

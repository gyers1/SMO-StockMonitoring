from __future__ import annotations

import math
import time
from functools import lru_cache
from threading import Lock
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict

from broker_settings import BrokerCredentials
from broker_transport import BrokerTransport
from broker_types import BrokerError, Quote

BASE: Final = 'https://openapi.koreainvestment.com:9443'


class KisToken(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    access_token: str = ''
    expires_in: int = 0


class KisPrice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    stck_shrn_iscd: str = ''
    stck_prpr: str = ''
    prdy_ctrt: str = ''
    rsym: str = ''
    last: str = ''
    rate: str = ''
    sign: str = ''


class KisResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    rt_cd: str
    msg_cd: str = ''
    output: KisPrice | None = None


def number(value: str) -> float:
    result = float(value.replace(',', '').strip())
    if not math.isfinite(result):
        raise BrokerError('한국투자증권 시세 값이 유효하지 않습니다.')
    return result


class KisClient:
    def __init__(self, key: str, secret: str) -> None:
        self.credentials = BrokerCredentials('kis', key, secret)
        self.wire = BrokerTransport()
        self.lock = Lock()
        self.token = ''
        self.expires = 0.0
        self.markets: dict[str, str] = {}

    def fetch(self, symbol: str) -> Quote:
        with self.lock:
            if not self.token or time.time() >= self.expires - 60:
                raw = self.wire.request(BASE + '/oauth2/tokenP', fields={
                    'grant_type': 'client_credentials', 'appkey': self.credentials.key,
                    'appsecret': self.credentials.secret})
                auth = KisToken.model_validate_json(raw)
                if not auth.access_token or auth.expires_in <= 60:
                    raise BrokerError('한국투자증권 인증 실패 · 실전용 App Key와 App Secret을 확인하세요.')
                self.token, self.expires = auth.access_token, time.time() + auth.expires_in
            try:
                return self._quote(symbol)
            except BrokerError as error:
                if error.code in (401, 403):
                    self.token = ''
                raise

    def _quote(self, symbol: str) -> Quote:
        domestic = symbol.endswith(('.KS', '.KQ'))
        code = symbol[:-3] if domestic else symbol
        markets = ('KRX',) if domestic else ((self.markets[code],) if code in self.markets else ('NAS', 'NYS', 'AMS'))
        for market in markets:
            fields = {'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code} if domestic else {'AUTH': '', 'EXCD': market, 'SYMB': code}
            path = '/uapi/domestic-stock/v1/quotations/inquire-price' if domestic else '/uapi/overseas-price/v1/quotations/price'
            raw = self.wire.request(BASE + path, fields=fields, token=self.token, get=True,
                                    api_id='FHKST01010100' if domestic else 'HHDFS00000300', kis=self.credentials)
            response = KisResponse.model_validate_json(raw)
            if response.rt_cd != '0':
                expired = response.msg_cd in ('EGW00121', 'EGW00123')
                raise BrokerError('한국투자증권 시세 조회 거절 · API 연결과 시세 권한을 확인하세요.', 401 if expired else 0)
            item = response.output
            if item is None or not (item.stck_prpr if domestic else item.last).strip():
                continue
            identity_matches = item.stck_shrn_iscd == code if domestic else item.rsym in (f'D{market}{code}', f'R{market}{code}')
            if not identity_matches:
                raise BrokerError('응답 종목이 달라 시세를 표시하지 않습니다.')
            price = number(item.stck_prpr if domestic else item.last)
            if price <= 0:
                raise BrokerError('현재가 미제공 · 거래 상태 또는 시세 권한을 확인하세요.')
            change_text = item.prdy_ctrt if domestic else item.rate
            change = number(change_text) if change_text.strip() else None
            if not domestic and change is not None:
                if item.sign in ('4', '5'):
                    change = -abs(change)
                elif item.sign in ('1', '2'):
                    change = abs(change)
                elif item.sign == '3':
                    change = 0.0
                else:
                    change = None
            self.markets[code] = market
            exchange = {'KRX': 'KRX', 'NAS': 'NASDAQ', 'NYS': 'NYSE', 'AMS': 'AMEX'}[market]
            return Quote(price, change, 'KRW' if domestic else 'USD', 0, symbol,
                         '한국투자증권', exchange, fetched_at=int(time.time()),
                         session='증권사 제공 시세' if domestic else '미국 시세 · 지연 가능')
        raise BrokerError('한국투자증권 시세 미제공 · 종목과 시세 이용 권한을 확인하세요.')


@lru_cache(maxsize=1)
def kis_client(key: str, secret: str) -> KisClient:
    return KisClient(key, secret)

from __future__ import annotations

import json
import socket
import time
from threading import Lock
from typing import Final, final

import httpx2
from broker_types import BrokerError
from broker_settings import BrokerCredentials

ALLOWED: Final = frozenset({
    ('https://openapi.tossinvest.com/oauth2/token', ''),
    ('https://openapi.tossinvest.com/api/v1/prices', ''),
    ('https://openapi.tossinvest.com/api/v1/rankings', ''),
    ('https://api.kiwoom.com/oauth2/token', 'au10001'),
    ('https://api.kiwoom.com/api/dostk/stkinfo', 'ka10001'),
    ('https://api.kiwoom.com/api/us/mrkcond', 'usa20100'),
    ('https://openapi.koreainvestment.com:9443/oauth2/tokenP', ''),
    ('https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price', 'FHKST01010100'),
    ('https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/price', 'HHDFS00000300'),
})


@final
class BrokerTransport:
    def __init__(self) -> None:
        self._lock = Lock()
        self._last = 0.0

    def request(self, url: str, *, fields: dict[str, str], token: str = '', api_id: str = '', form: bool = False, get: bool = False, kis: BrokerCredentials | None = None) -> bytes:
        if (url, api_id) not in ALLOWED:
            raise BrokerError('허용되지 않은 시세 요청입니다.')
        with self._lock:
            time.sleep(max(0, .36 - (time.monotonic() - self._last)))
            self._last = time.monotonic()
            headers = {'Accept': 'application/json'}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            if kis is not None:
                if not url.startswith('https://openapi.koreainvestment.com:9443/'):
                    raise BrokerError('한국투자증권 키를 다른 서버로 보낼 수 없습니다.')
                headers.update({'appkey': kis.key, 'appsecret': kis.secret,
                                'tr_id': api_id, 'custtype': 'P', 'Content-Type': 'application/json; charset=utf-8'})
            elif api_id:
                headers['api-id'] = api_id
            transport = httpx2.HTTPTransport(http2=True, retries=1,
                limits=httpx2.Limits(max_connections=4, max_keepalive_connections=2),
                socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)])
            try:
                with httpx2.Client(transport=transport, timeout=httpx2.Timeout(8, connect=5), follow_redirects=False) as client:
                    if get:
                        response = client.get(url, params=fields, headers=headers)
                    elif form:
                        response = client.post(url, data=fields, headers=headers)
                    else:
                        headers['Content-Type'] = 'application/json;charset=UTF-8'
                        response = client.post(url, content=json.dumps(fields).encode(), headers=headers)
            except httpx2.HTTPError:
                raise BrokerError('증권사 연결 실패 · 네트워크와 등록 IP를 확인하세요.') from None
            if response.status_code in (401, 403):
                raise BrokerError('인증 실패 · API 키, 등록 IP와 시세 이용 권한을 확인하세요.', response.status_code)
            if response.status_code == 429:
                raise BrokerError('증권사 조회 한도 초과 · 잠시 후 다시 조회합니다.')
            if response.status_code != 200:
                raise BrokerError(f'증권사 응답 오류 ({response.status_code}) · 설정을 확인하세요.')
            return response.content

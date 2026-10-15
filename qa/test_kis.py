import json
from unittest.mock import patch

import pytest

from broker_adapter import BrokerAdapter
from broker_transport import BrokerTransport
from broker_types import BrokerError


def test_kis_domestic_quote():
    # Given a valid KIS token and a Samsung quote.
    replies = [dict(access_token='test-token', expires_in=86400),
               dict(rt_cd='0', output=dict(stck_shrn_iscd='005930', stck_prpr='72000', prdy_ctrt='-1.25'))]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]) as wire:
        # When the configured broker loads the quote.
        quote = BrokerAdapter('kis', 'domestic-key', 'test-secret').fetch('005930.KS')
    # Then prices, source and exchange remain faithful to the response.
    assert (quote.price, quote.change_pct, quote.currency, quote.exchange, quote.timestamp) == (72000, -1.25, 'KRW', 'KRX', 0)
    assert wire.call_args.kwargs['api_id'] == 'FHKST01010100'


def test_kis_us_exchange_resolution():
    # Given no NAS quote and a NYSE quote with a negative change.
    replies = [dict(access_token='test-token', expires_in=86400),
               dict(rt_cd='0', output=dict(rsym='', last='')),
               dict(rt_cd='0', output=dict(rsym='DNYSIBM', last='250.125', rate='1.23', sign='5'))]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]):
        # When an American stock is requested.
        quote = BrokerAdapter('kis', 'us-key', 'test-secret').fetch('IBM')
    # Then its exchange, precision and sign are preserved.
    assert (quote.price, quote.change_pct, quote.currency, quote.exchange) == (250.125, -1.23, 'USD', 'NYSE')


@pytest.mark.parametrize('output', [
    dict(stck_shrn_iscd='000660', stck_prpr='72000', prdy_ctrt='0'),
    dict(stck_shrn_iscd='005930', stck_prpr='NaN', prdy_ctrt='0'),
    dict(stck_shrn_iscd='005930', stck_prpr='0', prdy_ctrt='0'),
])
def test_kis_rejects_bad_quotes(output):
    # Given an invalid or mismatched quote.
    replies = [dict(access_token='test-token', expires_in=86400), dict(rt_cd='0', output=output)]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]):
        # When that response reaches the adapter, then no price is displayed.
        with pytest.raises(BrokerError):
            BrokerAdapter('kis', json.dumps(output), 'test-secret').fetch('005930.KS')


def test_kis_uses_official_wire_contract_and_reuses_token():
    import httpx2
    from broker_kis import kis_client
    kis_client.cache_clear()
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == '/oauth2/tokenP':
            assert request.method == 'POST'
            assert json.loads(request.content) == {'grant_type': 'client_credentials', 'appkey': 'wire-key', 'appsecret': 'wire-secret'}
            return httpx2.Response(200, json={'access_token': 'wire-token', 'expires_in': 86400})
        assert request.method == 'GET'
        assert request.headers['authorization'] == 'Bearer wire-token'
        assert request.headers['appkey'] == 'wire-key'
        assert request.headers['appsecret'] == 'wire-secret'
        assert request.headers['tr_id'] == 'FHKST01010100'
        assert request.headers['custtype'] == 'P'
        assert request.url.params['FID_INPUT_ISCD'] == '005930'
        return httpx2.Response(200, json={'rt_cd': '0', 'output': {'stck_shrn_iscd': '005930', 'stck_prpr': '72000'}})

    with patch('broker_transport.httpx2.HTTPTransport', return_value=httpx2.MockTransport(respond)):
        first = BrokerAdapter('kis', 'wire-key', 'wire-secret').fetch('005930.KS')
        second = BrokerAdapter('kis', 'wire-key', 'wire-secret').fetch('005930.KS')
    assert first.price == second.price == 72000
    assert len(requests) == 3
    kis_client.cache_clear()


def test_kis_errors_hide_credentials():
    from quote_service import test_connection as probe
    with patch.object(BrokerTransport, 'request', return_value=b'{"error_description":"secret-private-value"}'):
        result = probe('kis', 'failure-key', 'secret-private-value')
    assert 'secret-private-value' not in result
    assert '실패' in result


def test_kis_us_rejects_wrong_symbol():
    replies = [dict(access_token='test-token', expires_in=86400),
               dict(rt_cd='0', output=dict(rsym='DNASMSFT', last='250', rate='1', sign='2'))]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]):
        with pytest.raises(BrokerError):
            BrokerAdapter('kis', 'wrong-us-key', 'test-secret').fetch('AAPL')

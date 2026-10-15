from quote_service import QuoteService

def test_unconfigured_service_has_no_fallback():
    service = QuoteService()
    service.request('005930.KS')
    assert service.get('005930.KS') is None
    assert service.status_text
    assert service.message('005930.KS')
    service.close()

import json
import time
from threading import Event
from unittest.mock import patch
import pytest
from broker_adapter import BrokerAdapter
from broker_transport import BrokerTransport
from broker_types import BrokerError, Quote
from quote_service import test_connection as probe


def wire(payloads):
    iterator = iter(payloads)
    def respond(self, url, **kwargs):
        return json.dumps(next(iterator)).encode()
    return respond


def test_toss_current_price_preserves_market_timestamp():
    payloads = [{'access_token': 'fixture-token', 'expires_in': 3600},
        {'result': [{'symbol': '005930', 'lastPrice': '72000', 'currency': 'KRW', 'timestamp': '2026-03-25T09:30:00.123+09:00'}]}]
    with patch.object(BrokerTransport, 'request', wire(payloads)):
        quote = BrokerAdapter('toss', 'fixture-key', 'fixture-secret').fetch('005930.KS')
    assert (quote.price, quote.currency, quote.timestamp, quote.change_pct) == (72000, 'KRW', 1774398600, None)


@pytest.mark.parametrize('symbol,currency,price', [('MSFT','USD','185.70'),('AAPL','KRW','185.70'),('AAPL','USD','NaN'),('AAPL','USD','-12')])
def test_toss_rejects_mismatched_or_invalid_price(symbol,currency,price):
    payloads = [{'access_token': 'fixture-token', 'expires_in': 3600},
        {'result': [{'symbol': symbol, 'lastPrice': price, 'currency': currency}]}]
    with patch.object(BrokerTransport, 'request', wire(payloads)), pytest.raises(BrokerError):
        BrokerAdapter('toss', 'fixture-key', 'fixture-secret').fetch('AAPL')


def test_toss_missing_timestamp_never_uses_receipt_time():
    payloads = [{'access_token': 'fixture-token', 'expires_in': 3600},
        {'result': [{'symbol': 'AAPL', 'lastPrice': '185.70', 'currency': 'USD', 'timestamp': None}]}]
    with patch.object(BrokerTransport, 'request', wire(payloads)):
        quote = BrokerAdapter('toss', 'fixture-key', 'fixture-secret').fetch('AAPL')
    assert quote.timestamp == 0 and quote.fetched_at > 0


def test_kiwoom_signed_price_is_absolute_but_change_signed():
    payloads = [{'token': 'fixture-token', 'expires_dt': '20990101120000'},
        {'return_code': 0, 'stk_cd': '005930', 'cur_prc': '-72000', 'flu_rt': '-2.15'}]
    with patch.object(BrokerTransport, 'request', wire(payloads)):
        quote = BrokerAdapter('kiwoom', 'fixture-key', 'fixture-secret').fetch('005930.KS')
    assert (quote.price, quote.change_pct, quote.currency, quote.timestamp) == (72000,-2.15,'KRW',0)


def test_kiwoom_us_resolves_exchange_and_keeps_usd_decimals():
    payloads = [{'token': 'fixture-token', 'expires_dt': '20990101120000'},
        {'return_code': 1903},
        {'return_code': 0, 'stk_cd': 'IBM', 'stex_tp': 'NY', 'cur_prc': '+251.1537', 'flu_rt': '+0.71', 'curr_unit': 'USD'}]
    with patch.object(BrokerTransport, 'request', wire(payloads)):
        quote = BrokerAdapter('kiwoom', 'fixture-key', 'fixture-secret').fetch('IBM')
    assert (quote.price, quote.exchange, quote.currency) == (251.1537,'NYSE','USD')


def test_auth_error_never_leaks_remote_response():
    with patch.object(BrokerTransport, 'request', wire([{'return_code':8001,'return_msg':'SECRET123'}])):
        result = probe('kiwoom','SECRET123','SECRET123')
    assert 'SECRET123' not in result


def test_mirae_and_unknown_broker_make_no_network_call():
    with patch.object(BrokerTransport,'request') as request:
        for provider in ('mirae','yahoo',''):
            assert probe(provider,'fixture-key','fixture-secret')
        request.assert_not_called()


def test_reconfiguration_drops_inflight_quote():
    started, release = Event(), Event()
    def fetch(self, symbol):
        started.set()
        assert release.wait(3)
        return Quote(100,None,'KRW',0)
    service = QuoteService()
    with patch.object(BrokerAdapter,'fetch',fetch):
        service.configure('toss','fixture-key','fixture-secret')
        service.request('005930.KS')
        assert started.wait(3)
        service.configure('','','')
        release.set()
        service._pool.shutdown(wait=True)
    assert service.get('005930.KS') is None and not service.configured
    service.close()


def test_token_is_cached_until_rejected():
    payloads = [{'access_token': 'fixture-token', 'expires_in': 3600},
        {'result': [{'symbol': 'AAPL', 'lastPrice': '185.70', 'currency': 'USD'}]},
        {'result': [{'symbol': 'AAPL', 'lastPrice': '186.70', 'currency': 'USD'}]}]
    with patch.object(BrokerTransport,'request',wire(payloads)):
        adapter = BrokerAdapter('toss','fixture-key','fixture-secret')
        adapter.fetch('AAPL')
        assert adapter.fetch('AAPL').price == 186.7


def test_transport_rejects_order_endpoint_before_network():
    with pytest.raises(BrokerError):
        BrokerTransport().request('https://api.kiwoom.com/api/dostk/ordr', fields={})

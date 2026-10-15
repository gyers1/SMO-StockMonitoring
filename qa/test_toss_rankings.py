import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from broker_adapter import BrokerAdapter
from broker_transport import BrokerTransport
from broker_types import BrokerError

STAMP = '2026-06-10T14:30:00+09:00'

@pytest.fixture(autouse=True)
def provider_clock():
    with patch('broker_toss.time.time', return_value=1781069410):
        yield

def ranking(symbol='005930', currency='KRW', rate='0.0125', last='56500', base='55800'):
    return dict(symbol=symbol, currency=currency, price=dict(lastPrice=last, basePrice=base, changeRate=rate))

def fetch_with(rows, symbol='005930.KS', stamp=STAMP, error=None):
    calls = []
    def respond(self, url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        if url.endswith('/rankings'):
            if error:
                raise error
            return json.dumps(dict(result=dict(rankings=rows, rankedAt=stamp))).encode()
        code = symbol[:-3] if symbol.endswith(('.KS', '.KQ')) else symbol
        currency = 'KRW' if symbol.endswith(('.KS', '.KQ')) else 'USD'
        return json.dumps(dict(result=[dict(symbol=code, lastPrice='777', currency=currency)])).encode()
    with patch.object(BrokerTransport, 'request', respond):
        quote = BrokerAdapter('toss', 'fixture', 'fixture').fetch(symbol)
    return quote, calls

@pytest.mark.parametrize('rate,expected', [('0.0125', 1.25), ('-0.0215', -2.15), ('0', 0)])
def test_daily_change_uses_provider_fraction_and_same_snapshot(rate, expected):
    # Given a provider ranking snapshot and a different current-price endpoint.
    # When the requested stock is covered by the ranking.
    quote, calls = fetch_with([ranking(rate=rate)])
    # Then price and daily change come from the same snapshot.
    assert (quote.price, quote.change_pct, quote.timestamp) == (56500, expected, 1781069400)
    assert not any(url.endswith('/prices') for url, _ in calls)
    assert calls[1][1]['fields'] == dict(type='MARKET_TRADING_AMOUNT', marketCountry='KR', duration='realtime', count='100')

def test_us_change_uses_usd_and_us_market():
    # Given a US ranking snapshot. When a US stock is requested.
    quote, calls = fetch_with([ranking('AAPL', 'USD', '-0.005', '225.51', '226.64')], 'AAPL')
    # Then USD decimals and market routing are preserved.
    assert (quote.price, quote.change_pct, quote.currency) == (225.51, -.5, 'USD')
    assert calls[1][1]['fields']['marketCountry'] == 'US'

@pytest.mark.parametrize('rows,stamp', [
    ([], STAMP), ([ranking(symbol='000660')], STAMP), ([ranking(currency='USD')], STAMP),
    ([ranking(rate=None)], STAMP), ([ranking(last='NaN')], STAMP), ([ranking(base='0')], STAMP),
    ([ranking(base=None)], STAMP), ([ranking(rate='Infinity')], STAMP), ([ranking()], None),
    ([ranking()], '2026-06-10T14:30:00'), ([ranking()], '2099-01-01T00:00:00+09:00'),
    ([ranking(), ranking()], STAMP),
    ([ranking()], '2026-06-10T14:28:59+09:00'),
])
def test_unusable_ranking_preserves_current_price_without_inventing_change(rows, stamp):
    # Given missing, malformed, or mismatched ranking data. When /prices is valid.
    quote, calls = fetch_with(rows, stamp=stamp)
    # Then current price survives and daily change stays unknown.
    assert quote.price == 777 and quote.change_pct is None and quote.change_note
    assert calls[-1][0].endswith('/prices')

@pytest.mark.parametrize('code', [0, 401, 403])
def test_ranking_failure_does_not_suppress_valid_price(code):
    # Given a ranking HTTP/authorization failure. When /prices still succeeds.
    quote, _ = fetch_with([], error=BrokerError('fixture', code))
    # Then the valid price is preserved.
    assert quote.price == 777 and quote.change_pct is None

def test_ranking_cache_is_shared_across_symbols_and_threads_then_expires():
    # Given one adapter used concurrently for multiple domestic stocks.
    calls = []
    clock = [10.0]
    def respond(self, url, **kwargs):
        calls.append(url)
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        return json.dumps(dict(result=dict(rankings=[ranking(), ranking('000660')], rankedAt=STAMP))).encode()
    adapter = BrokerAdapter('toss', 'fixture', 'fixture')
    with patch.object(BrokerTransport, 'request', respond), patch('broker_toss.time.monotonic', lambda: clock[0]):
        # When symbols are fetched in one cache window, then after it expires.
        with ThreadPoolExecutor(max_workers=4) as pool:
            quotes = list(pool.map(adapter.fetch, ['005930.KS', '000660.KS'] * 4))
        clock[0] = 15.1
        adapter.fetch('000660.KS')
    # Then each window makes a single market request with coherent quotes.
    assert len(quotes) == 8 and all(q.change_pct == 1.25 for q in quotes)
    assert sum(url.endswith('/rankings') for url in calls) == 2

def test_prices_auth_failure_invalidates_token_after_rankings_failure():
    # Given an expired token rejected by both optional ranking and required price.
    def respond(self, url, **kwargs):
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        raise BrokerError('fixture', 401)
    adapter = BrokerAdapter('toss', 'fixture', 'fixture')
    # When the quote is requested.
    with patch.object(BrokerTransport, 'request', respond), pytest.raises(BrokerError) as failure:
        adapter.fetch('AAPL')
    # Then authorization remains a real error and next fetch must reauthorize.
    assert failure.value.code == 401 and adapter._token == ''


def test_failed_ranking_is_cached_without_suppressing_other_prices():
    # Given an unavailable ranking endpoint and multiple stock requests.
    calls = []
    def respond(self, url, **kwargs):
        calls.append(url)
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        if url.endswith('/rankings'):
            raise BrokerError('fixture')
        return json.dumps(dict(result=[dict(symbol=kwargs['fields']['symbols'], currency='USD', lastPrice='25')])).encode()
    adapter = BrokerAdapter('toss', 'fixture', 'fixture')
    # When both quotes arrive in the same cache window.
    with patch.object(BrokerTransport, 'request', respond):
        quotes = [adapter.fetch('AAPL'), adapter.fetch('MSFT')]
    # Then the failure is cached and both current prices are still fetched.
    assert [q.price for q in quotes] == [25, 25]
    assert sum(url.endswith('/rankings') for url in calls) == 1
    assert sum(url.endswith('/prices') for url in calls) == 2


def test_rankings_cache_keeps_domestic_and_us_snapshots_separate():
    # Given domestic and US rankings on one adapter.
    markets = []
    def respond(self, url, **kwargs):
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        market = kwargs['fields']['marketCountry']
        markets.append(market)
        row = ranking() if market == 'KR' else ranking('AAPL', 'USD', '-0.005', '225.51', '226.64')
        return json.dumps(dict(result=dict(rankings=[row], rankedAt=STAMP))).encode()
    adapter = BrokerAdapter('toss', 'fixture', 'fixture')
    # When domestic, US and domestic quotes are requested.
    with patch.object(BrokerTransport, 'request', respond):
        quotes = [adapter.fetch('005930.KS'), adapter.fetch('AAPL'), adapter.fetch('005930.KS')]
    # Then each market is queried once and retains its currency/rate.
    assert markets == ['KR', 'US']
    assert [q.change_pct for q in quotes] == [1.25, -.5, 1.25]



@pytest.mark.parametrize('price_stamp', ['2026-06-10T14:28:58+09:00', '2026-06-10T14:28:59+09:00'])
def test_old_ranking_is_retained_when_current_price_confirms_snapshot(price_stamp):
    # Given an older ranking whose exact price remains the latest known trade.
    row = ranking()
    current = dict(symbol='005930', currency='KRW', lastPrice='56500.00', timestamp=price_stamp)
    def respond(self, url, **kwargs):
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        result = dict(rankings=[row], rankedAt='2026-06-10T14:28:59+09:00') if url.endswith('/rankings') else [current]
        return json.dumps(dict(result=result)).encode()
    # When the old ranking is independently checked through /prices.
    with patch.object(BrokerTransport, 'request', respond):
        quote = BrokerAdapter('toss', 'fixture', 'fixture').fetch('005930.KS')
    # Then the original ranking snapshot remains coherent, including its timestamp.
    assert (quote.price, quote.change_pct, quote.timestamp) == (56500, 1.25, 1781069339)
    assert quote.timestamp != quote.fetched_at


@pytest.mark.parametrize('last,price_stamp', [
    ('56501', '2026-06-10T14:28:58+09:00'),
    ('56500', '2026-06-10T14:29:00+09:00'),
    ('56500', '2026-06-10T14:28:59.001+09:00'),
    ('56500', None),
    ('56500.000000000001', '2026-06-10T14:28:58+09:00'),
])
def test_old_ranking_is_rejected_when_current_quote_cannot_confirm_snapshot(last, price_stamp):
    # Given a newer, different, or undated current-price observation.
    current = dict(symbol='005930', currency='KRW', lastPrice=last, timestamp=price_stamp)
    def respond(self, url, **kwargs):
        if url.endswith('/token'):
            return b'{"access_token":"fixture","expires_in":3600}'
        result = dict(rankings=[ranking()], rankedAt='2026-06-10T14:28:59+09:00') if url.endswith('/rankings') else [current]
        return json.dumps(dict(result=result)).encode()
    # When current price is compared with an older ranking.
    with patch.object(BrokerTransport, 'request', respond):
        quote = BrokerAdapter('toss', 'fixture', 'fixture').fetch('005930.KS')
    # Then only the current price is used, without cross-snapshot percentage.
    assert quote.price == float(last) and quote.change_pct is None

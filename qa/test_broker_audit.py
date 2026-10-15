import json
from unittest.mock import patch

import pytest

from broker_adapter import BrokerAdapter
from broker_transport import BrokerTransport
from quote_service import QuoteService


def test_kiwoom_wrapped_missing_exchange_continues_to_nyse():
    replies = [dict(token='fixture', expires_dt='20990101120000'),
               dict(return_code=7, return_msg='error[1903:instrument missing]'),
               dict(return_code=0, stk_cd='IBM', stex_tp='NY', curr_unit='USD', cur_prc='-226.8', flu_rt='-1.72')]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]):
        quote = BrokerAdapter('kiwoom', 'fixture', 'fixture').fetch('IBM')
    assert (quote.price, quote.change_pct, quote.exchange) == (226.8, -1.72, 'NYSE')


def test_unexpected_worker_failure_releases_pending_and_signals_error():
    service = QuoteService()
    adapter = BrokerAdapter('toss', 'fixture', 'fixture')
    service._pending.add('AAPL')
    with patch.object(BrokerAdapter, 'fetch', side_effect=RuntimeError('fixture bug')):
        with pytest.raises(RuntimeError):
            service._load('AAPL', adapter, service._generation)
    assert 'AAPL' not in service._pending
    assert service.error('AAPL')
    service.close()


def test_broker_error_can_pass_through_generator_context_manager():
    from contextlib import contextmanager
    from broker_types import BrokerError

    @contextmanager
    def scope():
        yield

    with pytest.raises(BrokerError):
        with scope():
            raise BrokerError('fixture network error')


@pytest.mark.parametrize('change', ['+1.25', '-1.25', '0.00', ''])
@pytest.mark.parametrize('provider', ['kiwoom', 'kis'])
def test_domestic_change_sign_and_absence_are_preserved(provider, change):
    from broker_kis import kis_client
    kis_client.cache_clear()
    if provider == 'kiwoom':
        replies = [dict(token='fixture', expires_dt='20990101120000'),
                   dict(return_code=0, stk_cd='005930', cur_prc='72000', flu_rt=change)]
    else:
        replies = [dict(access_token='fixture', expires_in=3600),
                   dict(rt_cd='0', output=dict(stck_shrn_iscd='005930', stck_prpr='72000', prdy_ctrt=change))]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]):
        quote = BrokerAdapter(provider, 'fixture', 'fixture').fetch('005930.KS')
    assert quote.change_pct == (float(change) if change else None)
    kis_client.cache_clear()


@pytest.mark.parametrize('sign,expected', [('1',1.25),('2',1.25),('3',0),('4',-1.25),('5',-1.25),('',None)])
def test_kis_us_change_follows_explicit_direction(sign, expected):
    from broker_kis import kis_client
    kis_client.cache_clear()
    replies = [dict(access_token='fixture', expires_in=3600),
               dict(rt_cd='0', output=dict(rsym='DNASAAPL', last='250', rate='1.25', sign=sign))]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]):
        quote = BrokerAdapter('kis', 'fixture', 'fixture').fetch('AAPL')
    assert quote.change_pct == expected
    kis_client.cache_clear()


def test_generic_kiwoom_code_seven_does_not_hide_other_errors():
    from broker_types import BrokerError
    replies = [dict(token='fixture', expires_dt='20990101120000'),
               dict(return_code=7, return_msg='server unavailable')]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]) as wire:
        with pytest.raises(BrokerError):
            BrokerAdapter('kiwoom', 'fixture', 'fixture').fetch('IBM')
    assert wire.call_count == 2


def test_toss_auth_rejection_is_reauthorized_on_next_request():
    from broker_types import BrokerError
    replies = [json.dumps(dict(access_token='first', expires_in=3600)).encode(),
               BrokerError('rejected', 401),
               json.dumps(dict(access_token='second', expires_in=3600)).encode(),
               json.dumps(dict(result=[dict(symbol='AAPL', lastPrice='250', currency='USD')])).encode()]
    adapter = BrokerAdapter('toss', 'fixture', 'fixture')
    with patch.object(BrokerTransport, 'request', side_effect=replies) as wire:
        with pytest.raises(BrokerError):
            adapter.fetch('AAPL')
        quote = adapter.fetch('AAPL')
    assert quote.price == 250
    assert wire.call_args.kwargs['token'] == 'second'


def test_transient_failure_preserves_last_price_but_marks_error():
    from broker_types import BrokerError, Quote
    service = QuoteService()
    adapter = BrokerAdapter('kiwoom', 'fixture', 'fixture')
    old = Quote(72000, -1.2, 'KRW', 0)
    service._quotes['005930.KS'] = old
    service._pending.add('005930.KS')
    with patch.object(BrokerAdapter, 'fetch', side_effect=BrokerError('network unavailable')):
        service._load('005930.KS', adapter, service._generation)
    assert service.get('005930.KS') == old
    assert service.error('005930.KS')
    assert '005930.KS' not in service._pending
    service.close()

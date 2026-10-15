import json
from unittest.mock import patch
import pytest
from broker_adapter import BrokerAdapter
from broker_transport import BrokerTransport

@pytest.mark.parametrize('current,expected', [('110',10),('90',-10),('100',0)])
def test_toss_quote_uses_previous_daily_close(current,expected):
    def respond(self,url,**kwargs):
        if url.endswith('/token'):
            result={'access_token':'fixture','expires_in':3600}
        elif url.endswith('/prices'):
            result={'result':[{'symbol':'069500','lastPrice':current,'currency':'KRW','timestamp':'2026-10-15T09:30:00+09:00'}]}
        else:
            assert url.endswith('/candles')
            assert kwargs['fields']['symbol']=='069500'
            result={'result':{'candles':[
                {'timestamp':'2026-10-15T00:00:00+09:00','closePrice':current,'currency':'KRW'},
                {'timestamp':'2026-10-14T00:00:00+09:00','closePrice':'100','currency':'KRW'}]}}
        return json.dumps(result).encode()
    with patch.object(BrokerTransport,'request',respond):
        quote=BrokerAdapter('toss','fixture','fixture').fetch('069500.KS')
    assert quote.change_pct==pytest.approx(expected)

from broker_toss_change import previous_close_change
from broker_types import Quote, BrokerError
from datetime import datetime

@pytest.mark.parametrize('base,currency,expected', [('100','USD',10),('0','USD',None),('NaN','USD',None),('100','KRW',None)])
def test_us_change_uses_exchange_day_not_korean_date(base,currency,expected):
    stamp=int(datetime.fromisoformat('2026-10-15T02:00:00+09:00').timestamp())
    quote=Quote(110,None,'USD',stamp,'AAPL')
    payload={'result':{'candles':[
        {'timestamp':'2026-10-14T00:00:00-04:00','closePrice':'110','currency':'USD'},
        {'timestamp':'2026-10-13T00:00:00-04:00','closePrice':base,'currency':currency}]}}
    with patch.object(BrokerTransport,'request',return_value=json.dumps(payload).encode()):
        actual=previous_close_change(BrokerTransport(),'fixture',quote)
    assert actual==expected

def test_missing_reference_keeps_valid_current_quote():
    quote=Quote(110,None,'USD',1774400000,'AAPL')
    with patch.object(BrokerTransport,'request',side_effect=BrokerError('unavailable')):
        assert previous_close_change(BrokerTransport(),'fixture',quote) is None

def test_unknown_trade_time_does_not_guess_previous_day():
    with patch.object(BrokerTransport,'request') as request:
        assert previous_close_change(BrokerTransport(),'fixture',Quote(110,None,'USD',0,'AAPL')) is None
        request.assert_not_called()

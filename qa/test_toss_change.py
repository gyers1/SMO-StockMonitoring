import json
from unittest.mock import patch

import pytest

from broker_adapter import BrokerAdapter
from broker_transport import BrokerTransport


@pytest.mark.parametrize('symbol,currency,price,stamp', [
    ('069500.KS', 'KRW', '85445', '2026-10-15T14:00:00+09:00'),
    ('005930.KS', 'KRW', '205500', '2026-10-15T14:00:00+09:00'),
    ('AAPL', 'USD', '346', '2026-10-15T02:00:00+09:00'),
    ('IBM', 'USD', '226.8', None),
])
def test_toss_preserves_price_but_does_not_invent_daily_change(symbol,currency,price,stamp):
    # Given only current price, no official daily base or change in this API.
    code = symbol[:-3] if symbol.endswith(('.KS', '.KQ')) else symbol
    replies = [dict(access_token='fixture', expires_in=3600),
               dict(result=[dict(symbol=code,lastPrice=price,currency=currency,timestamp=stamp)])]
    with patch.object(BrokerTransport, 'request', side_effect=[json.dumps(x).encode() for x in replies]) as wire:
        quote = BrokerAdapter('toss', 'fixture', 'fixture').fetch(symbol)
    # Then chart daily closes cannot masquerade as regular-session prior close.
    assert quote.price == float(price)
    assert quote.change_pct is None
    assert quote.change_note
    assert wire.call_count == 2
    assert wire.call_args.args[0].endswith('/prices')

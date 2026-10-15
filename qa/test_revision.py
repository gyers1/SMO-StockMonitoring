from quote_service import check_connection
from unittest.mock import patch
from broker_types import BrokerError, Quote


def test_probe_returns_machine_readable_success():
    with patch('broker_adapter.BrokerAdapter.fetch', return_value=Quote(100, None, 'KRW', 0)):
        result = check_connection('toss', 'fixture', 'fixture')
    assert result.success


def test_probe_failure_is_not_success():
    with patch('broker_adapter.BrokerAdapter.fetch', side_effect=BrokerError('denied')):
        result = check_connection('toss', 'fixture', 'fixture')
    assert not result.success

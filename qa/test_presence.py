from pathlib import Path
from unittest.mock import patch
import pytest
from PySide6.QtCore import QSettings, QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qt_model import TickerModel
from qt_island import GlassIsland
from qt_presence import AppPresence, claim_first_guide

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

def test_guide_claim_is_persisted_before_tutorial_finishes(tmp_path):
    path=tmp_path/'guide.ini'
    assert claim_first_guide(path)
    assert not claim_first_guide(path)

def test_existing_completed_guide_does_not_repeat(tmp_path):
    path=tmp_path/'guide.ini'
    settings=QSettings(str(path),QSettings.Format.IniFormat)
    settings.setValue('completed',True);settings.sync()
    assert not claim_first_guide(path)

def test_closing_window_preserves_service_and_tray_recovers_offscreen(app,tmp_path):
    with patch('qt_model.refresh_catalog'):
        model=TickerModel(tmp_path/'ticker_state.json')
    window=GlassIsland(model)
    presence=AppPresence(window)
    window.show();QTest.qWait(100)
    try:
        window.close();QTest.qWait(50)
        assert not window.isVisible()
        assert not model._closed
        window.anchor=QPointF(-99999,-99999)
        presence.restore();QTest.qWait(1000)
        assert window.isVisible()
        assert window.screen().availableGeometry().contains(window.geometry().center())
    finally:
        presence.tray.hide();presence.server.close()
        window.removeEventFilter(presence)
        model.close();window.hide()

def test_settings_replay_closes_modal_and_emits_request(app,tmp_path):
    from PySide6.QtTest import QSignalSpy
    from broker_settings import BrokerSettings
    from qt_broker_settings import BrokerSettingsDialog
    dialog=BrokerSettingsDialog(BrokerSettings(tmp_path/'credentials.json'))
    signal=QSignalSpy(dialog.guide_requested)
    dialog.show();QTest.qWait(100)
    dialog.guide_button.click();QTest.qWait(100)
    assert not dialog.isVisible()
    assert signal.count()==1

def test_second_launch_restores_hidden_window(app,tmp_path):
    from qt_presence import restore_running_app
    with patch('qt_model.refresh_catalog'):
        model=TickerModel(tmp_path/'ticker_state.json')
    window=GlassIsland(model);presence=AppPresence(window)
    try:
        window.hide()
        assert restore_running_app(tmp_path)
        QTest.qWait(500)
        assert window.isVisible()
    finally:
        presence.tray.hide();presence.server.close()
        window.removeEventFilter(presence);model.close();window.hide()

@pytest.mark.parametrize('percent,expected,color', [(None,'등락 —',None),(0.0,'0.00%',None),(1.2,'+1.20%',True),(-1.2,'-1.20%',False)])
def test_ribbon_distinguishes_unknown_flat_rise_fall(app,tmp_path,percent,expected,color):
    from broker_types import Quote
    from quote_service import QuoteService
    with patch('qt_model.refresh_catalog'):
        model=TickerModel(tmp_path/'ticker_state.json')
    window=GlassIsland(model)
    try:
        with patch.object(QuoteService,'get',return_value=Quote(100,percent,'KRW',0)):
            assert window.stock_text(0)[2:]==(expected,color)
    finally:
        model.close();window.hide()

def test_runtime_diagnostics_omits_messages_and_locals(tmp_path):
    import sys,faulthandler
    from runtime_diagnostics import install_diagnostics
    previous=sys.excepthook
    stream=install_diagnostics(tmp_path)
    try:
        try:
            raise RuntimeError('private-fixture-key-do-not-log')
        except RuntimeError as error:
            sys.excepthook(type(error),error,error.__traceback__)
        content=(tmp_path/'runtime.log').read_text(encoding='utf-8')
        assert 'RuntimeError' in content and 'test_presence.py' in content
        assert 'private-fixture-key-do-not-log' not in content
    finally:
        sys.excepthook=previous;faulthandler.disable()
        if stream is not None:stream.close()

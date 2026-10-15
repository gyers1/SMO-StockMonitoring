from __future__ import annotations
import sys
import tempfile
from functools import partial
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QTimer, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qt_app import configure_fonts
from qt_model import TickerModel
from qt_island import GlassIsland
from qt_presence import AppPresence, claim_first_guide, restore_running_app
from qt_onboarding import show_guide
from qt_broker_settings import BrokerSettingsDialog
from broker_types import Quote
from quote_service import QuoteService

app=QApplication([]);app.setQuitOnLastWindowClosed(False);configure_fonts(app)
output=ROOT/'qa/reliability';output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='SMO-presence-') as temp,patch('qt_model.refresh_catalog'):
    model=TickerModel(Path(temp)/'ticker_state.json')
    window=GlassIsland(model);window.guide_requested.connect(partial(show_guide,window))
    presence=AppPresence(window);window.show();QTest.qWait(200)
    assert claim_first_guide(Path(temp)/'guide.ini')
    show_guide(window);QTest.qWait(300)
    assert not claim_first_guide(Path(temp)/'guide.ini')
    window.guide_active.card.window().close();QTest.qWait(400)
    assert window.guide_active is None
    window.close();QTest.qWait(200)
    assert not window.isVisible() and not model._closed and presence.tray.isVisible()
    presence.menu.popup(app.primaryScreen().availableGeometry().center());QTest.qWait(200)
    presence.menu.grab().save(str(output/'tray-menu.png'))
    action=presence.menu.actions()[0]
    QTest.mouseClick(presence.menu,Qt.MouseButton.LeftButton,pos=presence.menu.actionGeometry(action).center())
    QTest.qWait(800);assert window.isVisible()
    window.grab().save(str(output/'restored-orb.png'))
    window.hide();assert restore_running_app(Path(temp));QTest.qWait(700);assert window.isVisible()
    window.anchor=QPointF(-99999,-99999);presence.restore();QTest.qWait(700)
    assert window.screen().availableGeometry().contains(window.geometry().center())
    def replay():
        dialog=next(d for d in window.dashboard.findChildren(BrokerSettingsDialog) if d.isVisible())
        dialog.grab().save(str(output/'settings.png'))
        QTest.mouseClick(dialog.guide_button,Qt.MouseButton.LeftButton)
    QTimer.singleShot(400,replay)
    window.dashboard.open_broker_settings();QTest.qWait(500)
    assert window.guide_active is not None
    guide=window.guide_active.card.window()
    guide.card.grab().save(str(output/'guide-replay.png'))
    guide.close();QTest.qWait(500)
    assert window.guide_active is None and not claim_first_guide(Path(temp)/'guide.ini')
    for percent,name in [(1.25,'rise'),(-1.25,'fall'),(0.0,'flat'),(None,'unknown')]:
        quote=Quote(85915,percent,'KRW',0,'069500.KS',change_note='등락률 미제공' if percent is None else '')
        with patch.object(QuoteService,'get',return_value=quote):
            window.transition('ribbon',True);QTest.qWait(900)
            window.grab().save(str(output/f'ribbon-{name}.png'))
            window.open_dashboard('watchlist');QTest.qWait(900)
            window.dashboard.refresh_quotes();window.grab().save(str(output/f'dashboard-{name}.png'))
    presence.shutdown();window.removeEventFilter(presence);window.hide()
print('PASS: tray-menu restore, duplicate launch restore, offscreen rescue, guide claim/skip/replay and four quote direction states')

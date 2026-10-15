from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPointF
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qt_island import GlassIsland
from qt_model import TickerModel
from qt_presence import AppPresence, restore_running_app


def test_relaunch_brings_existing_icon_to_current_monitor_center(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    with patch('qt_model.refresh_catalog'):
        model = TickerModel(tmp_path / 'ticker_state.json')
    window = GlassIsland(model)
    presence = AppPresence(window)
    screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
    assert screen is not None
    expected = QPointF(screen.availableGeometry().center()) - QPointF(18, 18)
    window.anchor = QPointF(screen.availableGeometry().topLeft()) + QPointF(20, 20)
    try:
        window.show()
        assert restore_running_app(tmp_path)
        QTest.qWait(700)
        assert window.anchor == expected
        assert window.isVisible()
    finally:
        presence.shutdown()
        window.removeEventFilter(presence)
        window.hide()


def test_relaunch_preserves_active_guide_geometry_and_step(tmp_path: Path) -> None:
    from qt_onboarding import show_guide
    app = QApplication.instance() or QApplication([])
    with patch('qt_model.refresh_catalog'):
        model = TickerModel(tmp_path / 'ticker_state.json')
    window = GlassIsland(model)
    presence = AppPresence(window)
    window.show()
    show_guide(window)
    QTest.qWait(800)
    guide = window.guide_active.card.window()
    anchor, geometry, index = QPointF(window.anchor), window.geometry(), guide.index
    try:
        assert restore_running_app(tmp_path)
        QTest.qWait(500)
        assert window.anchor == anchor
        assert window.geometry() == geometry
        assert guide.index == index
        assert guide.isVisible()
    finally:
        guide.close()
        QTest.qWait(300)
        presence.shutdown()
        window.removeEventFilter(presence)
        window.hide()

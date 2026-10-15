# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
# Run: .venv/Scripts/python.exe qa/check_broker_integration.py
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Final
from unittest.mock import patch

ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QWidget
from broker_adapter import BrokerAdapter
from broker_types import Quote
from qt_app import configure_fonts
from qt_broker_settings import BrokerSettingsDialog
from qt_island import GlassIsland
from qt_model import TickerModel


def click(widget: QWidget) -> None:
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=widget.rect().center())


def capture(widget: QWidget, name: str) -> None:
    assert widget.grab().save(str(ROOT / 'qa' / 'revision' / f'broker-fixture-{name}.png'))


def fixture_fetch(adapter: BrokerAdapter, symbol: str) -> Quote:
    domestic = symbol.endswith(('.KS', '.KQ'))
    return Quote(123456.0 if domestic else 234.56, 1.25, 'KRW' if domestic else 'USD', 0,
                 symbol, f'{adapter.name} FIXTURE', 'QA', None, int(time.time()), '검증용 고정 응답')


def main() -> None:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    configure_fonts(app)
    with tempfile.TemporaryDirectory(prefix='broker-ui-') as temp, patch('qt_model.refresh_catalog'), patch.object(BrokerAdapter, 'fetch', fixture_fetch):
        state = Path(temp) / 'state.json'
        state.write_text(json.dumps({'x': 140, 'y': 140, 'groups': {'검증용 FIXTURE': ['005930.KS', 'NVDA']}, 'selected_group': '검증용 FIXTURE'}), encoding='utf-8')
        model = TickerModel(state)
        window = GlassIsland(model)
        window.show()
        QCursor.setPos(1100, 800)
        try:
            window.open_dashboard('quotes')
            QTest.qWait(1100)
            dash = window.dashboard
            gear = next(button for button in dash.findChildren(QPushButton) if button.toolTip() == '증권사 API 설정')
            modal_seen: list[bool] = []

            def save_fixture() -> None:
                dialog = next(dialog for dialog in dash.findChildren(BrokerSettingsDialog) if dialog.isVisible())
                modal_seen.append(QApplication.activeModalWidget() is dialog)
                dialog.provider.setCurrentIndex(dialog.provider.findData('kiwoom'))
                QTest.keyClicks(dialog.key, 'FIXTURE-KEY-NOT-REAL')
                QTest.keyClicks(dialog.secret, 'FIXTURE-SECRET-NOT-REAL')
                capture(dialog, 'settings')
                click(dialog.save_button)
                QTimer.singleShot(600, dialog.reject)

            QTimer.singleShot(150, save_fixture)
            click(gear)
            QTest.qWait(1100)
            assert modal_seen == [True]
            assert model.quotes.configured
            stored = model.broker_settings.load()
            assert stored is not None and stored.provider == 'kiwoom'
            assert 'FIXTURE-KEY-NOT-REAL' not in model.broker_settings.path.read_text(encoding='utf-8')
            assert all('체결시각 미제공' in label.text() and '1970' not in label.text() for _, label in dash.price_labels)
            assert any('₩123,456' in label.text() for _, label in dash.price_labels)
            assert any('$234.56' in label.text() for _, label in dash.price_labels)
            capture(window, 'dashboard')

            def cancel_edit() -> None:
                dialog = next(dialog for dialog in dash.findChildren(BrokerSettingsDialog) if dialog.isVisible())
                dialog.key.setText('UNSAVED')
                click(next(button for button in dialog.findChildren(QPushButton) if button.text() == '닫기'))

            QTimer.singleShot(150, cancel_edit)
            click(gear)
            assert model.broker_settings.load() == stored
            window.transition('ribbon', True)
            QTest.qWait(1100)
            capture(window, 'ribbon')
            assert '123,456' in window.stock_text(0)[1]
            window.open_dashboard('watchlist')
            QTest.qWait(1100)

            def disconnect() -> None:
                dialog = next(dialog for dialog in dash.findChildren(BrokerSettingsDialog) if dialog.isVisible())
                click(dialog.delete_button)
                capture(dialog, 'disconnected-settings')
                dialog.reject()

            QTimer.singleShot(150, disconnect)
            click(gear)
            QTest.qWait(600)
            assert not model.quotes.configured
            assert model.quotes.get('005930.KS') is None
            assert all('API 설정 필요' in label.text() for _, label in dash.price_labels)
            capture(window, 'disconnected-dashboard')
            window.collapse()
            QTest.qWait(1100)
            orb_modal_seen: list[bool] = []

            def close_orb_settings() -> None:
                dialog = next(dialog for dialog in dash.findChildren(BrokerSettingsDialog) if dialog.isVisible())
                orb_modal_seen.append(QApplication.activeModalWidget() is dialog)
                dialog.reject()

            def choose_settings() -> None:
                menu = next(menu for menu in window.findChildren(QMenu) if menu.isVisible())
                action = next(action for action in menu.actions() if action.text() == '증권사 API 설정')
                QTimer.singleShot(150, close_orb_settings)
                QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())

            QTimer.singleShot(150, choose_settings)
            QTest.mouseClick(window, Qt.MouseButton.RightButton, pos=window.rect().center())
            assert orb_modal_seen == [True]
            print(json.dumps({'result': 'PASS', 'data': 'FIXTURE ONLY; no broker network or real credentials', 'checks': ['gear and orb context menu open actual modal', 'save applies to model and DPAPI encrypts key', 'KRW and USD fixture quotes render', 'missing timestamp has no 1970 date', 'cancel preserves prior credentials', 'disconnect clears displayed cached quotes']}, ensure_ascii=False))
        finally:
            window.close()
            app.processEvents()


if __name__ == '__main__':
    main()

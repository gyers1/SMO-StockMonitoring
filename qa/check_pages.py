# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
# Run: .venv/Scripts/python.exe qa/check_pages.py
from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qt_app import configure_fonts
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QPushButton, QScrollArea, QWidget
from qt_island import GlassIsland
from qt_model import TickerModel


def capture(window: QWidget, name: str) -> None:
    assert window.grab().save(str(ROOT / 'qa' / f'pages-{name}.png'))


def click(button: QWidget) -> None:
    QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=button.rect().center())


def native_click(widget: QWidget) -> None:
    QCursor.setPos(widget.mapToGlobal(widget.rect().center()))
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
    QTest.qWait(60)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
    QTest.qWait(900)


def main() -> None:
    app = QApplication([])
    configure_fonts(app)
    state = ROOT / 'qa' / 'pages-state.json'
    state.write_text(json.dumps({'x': 150, 'y': 150, 'groups': {'반도체': ['005930.KS', '000660.KS', 'NVDA']}, 'selected_group': '반도체'}), encoding='utf-8')
    model = TickerModel(state)
    window = GlassIsland(model)
    helper = QWidget()
    helper.setWindowTitle('Ticker QA outside-click target')
    helper.setGeometry(760, 160, 220, 140)
    helper.show()
    window.show()
    try:
        QCursor.setPos(1100, 800)
        window.transition('ribbon', True)
        QTest.qWait(1200)
        capture(window, 'ribbon')
        body = window.body()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(round(body.right() - 79), round(body.center().y())))
        QTest.qWait(1200)
        dash = window.dashboard
        assert window.mode == 'dashboard' and dash.page == 'quotes'
        assert dash.entry.isVisible()
        capture(window, 'quotes')
        scroll = dash.findChild(QScrollArea)
        assert scroll is not None
        height = scroll.height()
        dash.entry.setText('삼')
        QTest.qWait(1500)
        assert len(dash.dropdown.rows) == 5 and dash.dropdown.isVisible()
        assert scroll.height() == height, (height, scroll.height())
        capture(window, 'dropdown')
        index = next(i for i, stock in enumerate(model.results) if stock.symbol not in model.groups[model.selected_group])
        chosen = model.results[index]
        click(dash.dropdown.rows[index])
        QTest.qWait(100)
        assert chosen.symbol in model.groups[model.selected_group]
        assert dash.motion.isVisible()
        assert '추가됨' in dash.status.text(), dash.status.text()
        capture(window, 'add-mid')
        QTest.qWait(700)
        assert not dash.motion.isVisible()
        assert not dash.dropdown.isVisible()
        capture(window, 'add-settled')
        dash.entry.setText(chosen.name)
        QTest.qWait(150)
        duplicate_index = next(i for i, stock in enumerate(model.results) if stock.symbol == chosen.symbol)
        count = len(model.groups[model.selected_group])
        click(dash.dropdown.rows[duplicate_index])
        assert len(model.groups[model.selected_group]) == count
        assert '이미 추가됨' in dash.status.text()
        back = next(button for button in dash.findChildren(QPushButton) if button.toolTip() == '한 줄 시세로 돌아가기')
        click(back)
        QTest.qWait(1100)
        assert window.mode == 'ribbon'
        body = window.body()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=QPoint(round(body.right() - 49), round(body.center().y())))
        QTest.qWait(1200)
        assert dash.page == 'watchlist' and not dash.entry.isVisible() and not dash.dropdown.isVisible()
        assert scroll.height() > height
        capture(window, 'watchlist')
        menu = QMenu(dash)
        menu.addAction('QA menu')
        menu.popup(helper.mapToGlobal(QPoint(10, 10)))
        QTest.qWait(100)
        native_click(menu)
        assert window.mode == 'dashboard', 'app menu click collapsed dashboard'
        menu.close()
        dialog = QDialog(window)
        dialog.setModal(True)
        dialog.setGeometry(760, 330, 220, 120)
        dialog.show()
        QTest.qWait(100)
        native_click(dialog)
        assert window.mode == 'dashboard', 'app modal click collapsed dashboard'
        dialog.close()
        QTest.qWait(100)
        native_click(helper)
        assert window.mode == 'orb', f'outside click failed: {window.mode}'
        capture(window, 'outside-orb')
        print(json.dumps({'result': 'PASS', 'autocomplete_rows': 5, 'search_watch_height': height, 'watchlist_height': scroll.height(), 'motion': 'visible at 100ms and settled after 800ms', 'duplicates': 'no duplicate persisted', 'navigation': 'magnifier quotes, star watchlist, back ribbon', 'outside_click': 'native mouse on QA helper collapses', 'exceptions': 'native menu and modal clicks do not collapse'}, ensure_ascii=False))
    finally:
        helper.close()
        window.close()
        app.processEvents()


if __name__ == '__main__':
    main()

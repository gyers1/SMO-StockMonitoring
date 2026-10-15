from __future__ import annotations

import time
from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from qt_model import TickerModel
from qt_add_motion import AddMotion
from qt_search_dropdown import SearchDropdown
from stock_catalog import Stock

from qt_styles import STYLE
from qt_market import MarketBadge, money


class ElidedLabel(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.full_text = text
        self.setToolTip(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, self.width()))
        super().resizeEvent(event)


class SearchEntry(QLineEdit):
    navigate = Signal(int)
    dismissed = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.dismissed.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self.navigate.emit(1 if event.key() == Qt.Key.Key_Down else -1)
            event.accept()
            return
        super().keyPressEvent(event)


class Dashboard(QWidget):
    back_requested = Signal()
    interaction_started = Signal()
    stock_selected = Signal()

    def __init__(self, model: TickerModel) -> None:
        super().__init__()
        self.model = model
        self.page = "quotes"
        self.search_dismissed = False
        self.watch_rows: dict[str, QFrame] = {}
        self.selected = 0
        self.price_labels: list[tuple[str, QLabel]] = []
        self.result_rows: list[QPushButton] = []
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)
        header = QHBoxLayout()
        self.title = QLabel("시세 페이지")
        self.title.setObjectName("title")
        header.addWidget(self.title)
        header.addStretch()
        self.settings_button = self.button("⚙", "증권사 API 설정", self.open_broker_settings)
        header.addWidget(self.settings_button)
        back = self.button("←  한 줄로", "한 줄 시세로 돌아가기", self.back_requested.emit)
        back.setStyleSheet("background: rgba(160,189,219,25); font-weight: 600; padding: 4px 12px;")
        self.back_button = back
        header.addWidget(back)
        root.addLayout(header)
        self.entry = SearchEntry()
        self.entry.setPlaceholderText("회사명 또는 종목코드")
        self.entry.setClearButtonEnabled(True)
        self.entry.textChanged.connect(self.search_changed)
        self.entry.navigate.connect(self.navigate)
        self.entry.returnPressed.connect(self.add_selected)
        root.addWidget(self.entry)
        self.hint = QLabel("한글로 검색 · 코스피 · 코스닥 · 해외")
        self.hint.setObjectName("muted")
        root.addWidget(self.hint)
        self.dropdown = SearchDropdown(self, model)
        self.dropdown.chosen.connect(self.add_index)
        self.entry.dismissed.connect(self.dismiss_results)
        self.motion = AddMotion(self)
        self.motion.finished.connect(self.clear_highlight)
        toolbar = QHBoxLayout()
        self.group = QComboBox()
        self.group.setMinimumWidth(150)
        self.group.currentTextChanged.connect(model.set_group)
        toolbar.addWidget(self.group, 1)
        toolbar.addWidget(self.button("···", "그룹 관리", self.group_menu))
        root.addLayout(toolbar)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.watchlist = QWidget()
        self.watch_layout = QVBoxLayout(self.watchlist)
        self.watch_layout.setContentsMargins(0, 0, 3, 0)
        self.watch_layout.setSpacing(5)
        self.watch_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.watchlist)
        root.addWidget(self.scroll_area, 1)
        self.provenance = ElidedLabel("")
        self.provenance.setObjectName("muted")
        root.addWidget(self.provenance)
        self.status = QLabel("가격 아래는 시세 시각 · 상세 정보는 가격에 마우스를 올리세요")
        self.status.setObjectName("muted")
        root.addWidget(self.status)
        model.changed.connect(self.render_groups)
        model.results_changed.connect(self.render_results)
        model.quotes_updated.connect(self.refresh_quotes)
        self.render_groups()
        self.render_results()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def open_broker_settings(self) -> None:
        from qt_broker_settings import BrokerSettingsDialog
        self.interaction_started.emit()
        self.dismiss_results()
        dialog = BrokerSettingsDialog(self.model.broker_settings, self)
        dialog.applied.connect(self.model.reload_broker)
        dialog.exec()

    def show_page(self, page: str) -> None:
        self.stop_feedback()
        self.page = page
        searching = page == "quotes"
        self.title.setText("시세 페이지" if searching else "관심종목 페이지")
        self.entry.setVisible(searching)
        self.hint.setVisible(searching)
        self.dismiss_results()

    def stop_feedback(self) -> None:
        self.motion.stop()
        self.dropdown.hide()

    def clear_highlight(self) -> None:
        for row in self.watch_rows.values():
            row.setStyleSheet("")

    def search_changed(self, text: str) -> None:
        self.search_dismissed = False
        self.selected = 0
        self.model.set_query(text)

    def dismiss_results(self) -> None:
        self.search_dismissed = True
        self.dropdown.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self.isVisible() and event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            point = self.mapFromGlobal(event.globalPosition().toPoint())
            if self.dropdown.isVisible() and not self.dropdown.geometry().contains(point) and not self.entry.geometry().contains(point):
                self.dismiss_results()
            elif watched is self.entry and self.page == "quotes" and self.model.results:
                self.search_dismissed = False
                self.render_results()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.dropdown.anchor(self.entry)

    def button(self, text: str, tooltip: str, action: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(27)
        button.clicked.connect(action)
        return button

    def clear_rows(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                labels = widget.findChildren(QLabel)
                self.price_labels = [(s, label) for s, label in self.price_labels if label not in labels]
                widget.deleteLater()

    def row(self, stock: Stock) -> QFrame:
        row = QFrame()
        row.setObjectName("row")
        row.setFixedHeight(51)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(9, 5, 5, 5)
        layout.setSpacing(3)
        labels = QVBoxLayout()
        labels.setSpacing(1)
        name = ElidedLabel(stock.name)
        name.setStyleSheet("font-weight: 600;")
        labels.addWidget(name)
        market = MarketBadge(stock)
        market.setObjectName("muted")
        market.setToolTip(f"{stock.market} · {stock.symbol}")
        labels.addWidget(market)
        layout.addLayout(labels, 1)
        price = QLabel()
        price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        price.setMinimumWidth(112)
        price.setStyleSheet("font-size: 10px;")
        layout.addWidget(price)
        self.price_labels.append((stock.symbol, price))
        for text, tip, action in (("↑", "앞으로 이동", partial(self.model.move_stock, stock.symbol, -1)),
                                  ("↓", "뒤로 이동", partial(self.model.move_stock, stock.symbol, 1)),
                                  ("×", "그룹에서 제거", partial(self.model.remove_stock, stock.symbol))):
            button = self.button(text, tip, action)
            button.setFixedWidth(22)
            layout.addWidget(button)
        return row

    def render_groups(self) -> None:
        self.motion.stop()
        self.group.blockSignals(True)
        self.group.clear()
        self.group.addItems(list(self.model.groups))
        self.group.setCurrentText(self.model.selected_group)
        self.group.blockSignals(False)
        self.clear_rows(self.watch_layout)
        self.watch_rows.clear()
        for symbol in self.model.groups[self.model.selected_group]:
            row = self.row(self.model.stocks[symbol])
            self.watch_layout.addWidget(row)
            self.watch_rows[symbol] = row
        if not self.model.groups[self.model.selected_group]:
            empty = QLabel("시세 페이지에서 종목을 검색해 담아보세요.")
            empty.setObjectName("muted")
            self.watch_layout.addWidget(empty)
        self.render_results()
        self.status.setText(self.model.storage_error or "가격 아래는 시세 시각 · 상세 정보는 가격에 마우스를 올리세요")

    def render_results(self) -> None:
        self.dropdown.populate(self.model.results)
        self.result_rows = self.dropdown.rows
        self.selected = min(self.selected, max(0, len(self.result_rows) - 1))
        self.hint.setText(self.model.search_status or "한글로 검색 · 코스피 · 코스닥 · 해외")
        self.navigate(0)
        self.dropdown.anchor(self.entry)
        self.dropdown.setVisible(self.page == "quotes" and bool(self.result_rows) and not self.search_dismissed)
        self.refresh_quotes()

    def refresh_quotes(self) -> None:
        source = self.model.broker_error or self.model.quotes.status_text
        self.provenance.full_text = source
        self.provenance.setText(self.provenance.fontMetrics().elidedText(source, Qt.TextElideMode.ElideRight, self.provenance.width()))
        self.provenance.setToolTip(source)
        self.dropdown.refresh_quotes()
        for symbol, label in self.price_labels:
            quote = self.model.quotes.get(symbol)
            failed = self.model.quotes.error(symbol)
            if quote is None:
                message = self.model.quotes.message(symbol)
                label.setText("시세 확인 필요" if failed else "API 설정 필요" if not self.model.quotes.configured else "가격 확인 중…")
                label.setToolTip(message)
                continue
            label.setToolTip(quote.tooltip + ("\n갱신 실패 · 마지막으로 받은 가격" if failed else ""))
            change = "" if quote.change_pct is None else f" {quote.change_pct:+.2f}%"
            stamp = time.strftime("%m/%d %H:%M", time.localtime(quote.timestamp)) if quote.timestamp else "체결시각 미제공"
            label.setText(f"{money(quote.price, quote.currency)}\n{'이전 시세 · ' if failed else change + ' · '}{stamp}")

    def navigate(self, direction: int) -> None:
        if not self.result_rows:
            return
        self.selected = (self.selected + direction) % len(self.result_rows)
        self.dropdown.select(self.selected)
        if direction and self.page == "quotes":
            self.search_dismissed = False
            self.dropdown.show()
            self.dropdown.raise_()

    def add_selected(self) -> None:
        if self.dropdown.isVisible():
            self.add_index(self.selected)

    def add_index(self, index: int) -> None:
        if index >= len(self.model.results):
            return
        stock = self.model.results[index]
        if stock.symbol in self.model.groups[self.model.selected_group]:
            self.stock_selected.emit()
            self.status.setText(f"{stock.name} · 이미 추가됨")
            self.dismiss_results()
            return
        source = self.result_rows[index]
        snapshot = source.grab()
        origin = QRect(source.mapTo(self, QPoint()), source.size())
        self.dismiss_results()
        self.model.add_stock(stock)
        if self.model.storage_error:
            self.status.setText(self.model.storage_error)
            self.status.setToolTip(self.model.storage_error)
            return
        self.stock_selected.emit()
        self.status.setText(f"{stock.name} · {self.model.selected_group} 그룹에 추가됨")
        target = self.watch_rows[stock.symbol]
        self.watch_layout.activate()
        self.scroll_area.ensureWidgetVisible(target, 0, 8)
        target.setStyleSheet("QFrame#row { background: rgba(230,161,106,24); border: 1px solid rgba(230,161,106,70); border-radius: 10px; }")
        self.motion.start(snapshot, origin, QRect(target.mapTo(self, QPoint()), target.size()))

    def group_menu(self) -> None:
        self.interaction_started.emit()
        menu = QMenu(self)
        menu.addAction("새 그룹", partial(self.edit_group, False))
        menu.addAction("그룹 이름 변경", partial(self.edit_group, True))
        delete = menu.addAction("현재 그룹 삭제", self.delete_group)
        delete.setEnabled(len(self.model.groups) > 1)
        menu.exec(self.mapToGlobal(self.rect().center()))

    def edit_group(self, rename: bool) -> None:
        name, accepted = QInputDialog.getText(self, "그룹 이름", "그룹 이름을 입력하세요.",
                                             text=self.model.selected_group if rename else "")
        if accepted and name.strip():
            success = self.model.rename_group(name.strip()) if rename else self.model.create_group(name.strip())
            if not success:
                QMessageBox.information(self, "그룹 이름", "이미 있는 그룹 이름입니다.")

    def delete_group(self) -> None:
        answer = QMessageBox.question(self, "그룹 삭제", f"'{self.model.selected_group}' 그룹을 삭제할까요?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.model.delete_group()

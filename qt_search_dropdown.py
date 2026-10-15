from __future__ import annotations

from functools import partial

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from qt_model import TickerModel
from stock_catalog import Stock
from qt_market import MarketBadge, money


class ResultName(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.full_text = text
        self.setToolTip(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, self.width()))
        super().resizeEvent(event)


class SearchDropdown(QFrame):
    chosen = Signal(int)

    def __init__(self, parent: QWidget, model: TickerModel) -> None:
        super().__init__(parent)
        self.host = parent
        self.model = model
        self.rows: list[QPushButton] = []
        self.prices: list[tuple[Stock, QLabel]] = []
        self.setObjectName("searchDropdown")
        self.setStyleSheet("""
            QFrame#searchDropdown { background: #101522; border: 1px solid #394355;
                border-radius: 12px; }
            QPushButton { background: transparent; border: none; border-radius: 6px; padding: 0; }
            QPushButton:hover, QPushButton[selected="true"] { background: #293D53; }
            QLabel { background: transparent; color: #ECEEF2; font-size: 11px; }
        """)
        self.layout_rows = QVBoxLayout(self)
        self.layout_rows.setContentsMargins(5, 5, 5, 5)
        self.layout_rows.setSpacing(1)
        self.hide()

    def populate(self, stocks: list[Stock]) -> None:
        self.prices.clear()
        self.rows.clear()
        while self.layout_rows.count():
            item = self.layout_rows.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()
        for index, stock in enumerate(stocks[:5]):
            row = QPushButton()
            row.setFixedHeight(34)
            row.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setAccessibleName(f"{stock.name} 관심 그룹에 추가")
            row.setToolTip(f"{stock.name} · {stock.market} · {stock.symbol}")
            line = QHBoxLayout(row)
            line.setContentsMargins(8, 0, 7, 0)
            line.setSpacing(6)
            name = ResultName(stock.name)
            name.setMinimumWidth(0)
            name.setStyleSheet("font-weight: 600;")
            name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            line.addWidget(name, 1)
            market = MarketBadge(stock, compact=True)
            market.setStyleSheet("color: #B0B3BC; font-size: 9px;")
            market.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            line.addWidget(market)
            price = QLabel("확인 중…")
            price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            line.addWidget(price)
            add = QLabel("✓" if stock.symbol in self.model.groups[self.model.selected_group] else "+")
            add.setStyleSheet("color: #E6A16A; font-size: 15px;")
            add.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            line.addWidget(add)
            row.clicked.connect(partial(self.chosen.emit, index))
            self.rows.append(row)
            self.prices.append((stock, price))
            self.layout_rows.addWidget(row)
        self.setFixedHeight(10 + len(self.rows) * 35)
        self.refresh_quotes()

    def anchor(self, entry: QWidget) -> None:
        self.move(entry.mapTo(self.host, QPoint(0, entry.height() + 4)))
        self.setFixedWidth(entry.width())
        self.raise_()

    def select(self, index: int) -> None:
        for number, row in enumerate(self.rows):
            row.setProperty("selected", number == index)
            row.style().unpolish(row)
            row.style().polish(row)

    def refresh_quotes(self) -> None:
        for index, (stock, label) in enumerate(self.prices):
            quote = self.model.quotes.get(stock.symbol)
            failed = self.model.quotes.error(stock.symbol)
            if quote is None:
                label.setText("확인 필요" if failed else "API 설정 필요" if not self.model.quotes.configured else "확인 중…")
                self.rows[index].setToolTip(f"{stock.name} · {stock.market} · {stock.symbol}\n{self.model.quotes.message(stock.symbol)}")
                continue
            self.rows[index].setToolTip(f"{stock.name} · {stock.market} · {stock.symbol}\n{quote.tooltip}" + ("\n갱신 실패 · 이전 시세" if failed else ""))
            label.setText(money(quote.price, quote.currency) + (" · 이전" if failed else ""))

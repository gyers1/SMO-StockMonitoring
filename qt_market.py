from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from stock_catalog import Stock

FLAGS: Final = {'한국': 'kr', '미국': 'us', '일본': 'jp', '중국': 'cn', '홍콩': 'hk', '영국': 'gb', '캐나다': 'ca', '호주': 'au', '독일': 'de', '프랑스': 'fr'}
SYMBOLS: Final = {'KRW': '₩', 'USD': '$', 'JPY': '¥', 'CNY': 'CN¥', 'HKD': 'HK$', 'GBP': '£', 'CAD': 'CA$', 'AUD': 'A$', 'EUR': '€'}


def money(price: float, currency: str) -> str:
    amount = f'{price:,.0f}' if currency in ('KRW', 'JPY') else f'{price:,.2f}'
    return f'{SYMBOLS.get(currency, currency + " ")}{amount}'


class MarketBadge(QWidget):
    def __init__(self, stock: Stock, *, compact: bool = False) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setToolTip(f'{stock.market} · {stock.symbol} · {stock.currency}')
        self.setAccessibleName(stock.market)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(5)
        country, separator, exchange = stock.market.partition(' · ')
        flag = FLAGS.get(country)
        if flag:
            picture = QLabel()
            picture.setFixedSize(18, 14)
            pixmap = QPixmap(str(Path(__file__).resolve().parent / 'assets' / 'flags' / f'{flag}.svg'))
            picture.setPixmap(pixmap.scaled(18, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            row.addWidget(picture)
        if not compact or not flag:
            text = QLabel(exchange if flag and separator else stock.market)
            text.setStyleSheet('color:#B0B3BC; font-size:10px;')
            row.addWidget(text)
        row.addStretch()

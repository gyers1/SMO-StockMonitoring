"""Qt-owned watchlist state; all remote work stays outside the UI thread."""
from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, QTimer, Signal

from app_paths import DATA_DIR
from quote_service import QuoteService
from broker_settings import BrokerSettings, SettingsError
from stock_catalog import Stock, catalog, refresh_catalog, search, search_remote


class TickerModel(QObject):
    """Mutable application model, with Qt signals emitted on its owning thread."""

    changed = Signal()
    quotes_updated = Signal()
    results_changed = Signal()

    def __init__(self, state_path: Path | None = None) -> None:
        super().__init__()
        self.state_path = state_path or DATA_DIR / "ticker_state.json"
        self.storage_error = ""
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        except (OSError, ValueError) as error:
            raw = {}
            self.storage_error = str(error)
        self._original = raw if isinstance(raw, dict) else {}
        raw = self._original
        x_value, y_value = raw.get("x"), raw.get("y")
        self.x: int = x_value if isinstance(x_value, int) else 80
        self.y: int = y_value if isinstance(y_value, int) else 40
        recent = raw.get("recent", [])
        self.recent: list[str] = [s for s in recent if isinstance(s, str)] if isinstance(recent, list) else []
        symbol = raw.get("symbol", "000660.KS")
        self.symbol: str = symbol if isinstance(symbol, str) else "000660.KS"
        groups = raw.get("groups", {})
        self.groups: dict[str, list[str]] = {}
        if isinstance(groups, dict):
            self.groups = {name: list(dict.fromkeys(s for s in items if isinstance(s, str)))
                           for name, items in groups.items()
                           if isinstance(name, str) and name.strip() and isinstance(items, list)}
        if not self.groups:
            self.groups = {"관심": list(dict.fromkeys([self.symbol, *self.recent]))}
        chosen = raw.get("selected_group")
        self.selected_group: str = chosen if isinstance(chosen, str) and chosen in self.groups else next(iter(self.groups))
        self.stocks: dict[str, Stock] = {stock.symbol: stock for stock in catalog()}
        names = raw.get("stock_names", {})
        if isinstance(names, dict):
            for key, item in names.items():
                if isinstance(key, str) and isinstance(item, list) and len(item) == 3 and all(isinstance(v, str) for v in item):
                    self.stocks.setdefault(key, Stock(key, item[0], item[1], item[2]))
        self.stocks.setdefault("SKHY", Stock("SKHY", "SK하이닉스 ADR", "미국 · 나스닥 · ADR", "USD"))
        for key in [*self.recent, *(s for items in self.groups.values() for s in items)]:
            self.stocks.setdefault(key, Stock(key, key, "시장 확인 필요", ""))
        self.results: list[Stock] = []
        self.query = ""
        self.search_status = "회사명 검색 · 한글 가능"
        self.quotes = QuoteService()
        self.broker_settings = BrokerSettings(state_path.with_name("broker_credentials.json") if state_path else None)
        self.broker_error = ""
        self.reload_broker()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search")
        self._pending: Future[list[Stock]] | None = None
        self._pending_query = ""
        self._closed = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._start_remote)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._catalog_worker = Thread(target=refresh_catalog, daemon=True, name="catalog")
        self._catalog_worker.start()
        self._catalog_applied = False
        self._poll()

    def reload_broker(self) -> None:
        self.broker_error = ""
        try:
            credentials = self.broker_settings.load()
        except SettingsError:
            credentials = None
            self.broker_error = "연결 정보를 읽지 못했습니다. 설정에서 다시 저장해 주세요."
        if credentials is None:
            self.quotes.configure("", "", "")
        else:
            self.quotes.configure(credentials.provider, credentials.key, credentials.secret)
        self.quotes_updated.emit()

    def set_query(self, query: str) -> None:
        self.query = query.strip()
        self._debounce.stop()
        if self._pending is not None:
            self._pending.cancel()
            self._pending = None
        self.results = search(self.query, self.groups[self.selected_group]) if self.query else []
        self.search_status = "회사명 검색 · 한글 가능"
        if self.query:
            self.search_status = "종목을 선택하면 관심 그룹에 추가" if self.results else "온라인 검색 중…"
        if self.query and not self.results:
            self._debounce.start()
        self.results_changed.emit()
        self._request_quotes()

    def _start_remote(self) -> None:
        self._pending_query = self.query
        self._pending = self._pool.submit(search_remote, self.query)

    def _request_quotes(self) -> None:
        for symbol in dict.fromkeys([*self.groups[self.selected_group], *(s.symbol for s in self.results)]):
            self.quotes.request(symbol)

    def _poll(self) -> None:
        if not self._catalog_applied and not self._catalog_worker.is_alive():
            self._catalog_applied = True
            self.stocks.update((stock.symbol, stock) for stock in catalog())
            if self.query:
                self.set_query(self.query)
            self.changed.emit()
        if self._pending is not None and self._pending.done():
            pending, query = self._pending, self._pending_query
            self._pending = None
            if not pending.cancelled() and query == self.query:
                try:
                    self.results = pending.result()
                    self.search_status = "종목을 선택하면 관심 그룹에 추가" if self.results else "일치하는 종목이 없습니다"
                except (OSError, ValueError, LookupError, TypeError):
                    self.results = []
                    self.search_status = "온라인 검색 연결 실패 · 잠시 후 다시 입력해 주세요"
                self.stocks.update((stock.symbol, stock) for stock in self.results)
                self.results_changed.emit()
        self._request_quotes()
        self.quotes_updated.emit()

    def set_group(self, name: str) -> None:
        if name not in self.groups:
            return
        self.selected_group = name
        self.set_query(self.query)
        self.save()
        self.changed.emit()

    def add_stock(self, stock: Stock) -> None:
        self.stocks[stock.symbol] = stock
        items = self.groups[self.selected_group]
        if stock.symbol not in items:
            items.append(stock.symbol)
        self.symbol = stock.symbol
        self.recent = [stock.symbol, *(s for s in self.recent if s != stock.symbol)][:6]
        self._request_quotes()
        self.save()
        self.changed.emit()

    def remove_stock(self, symbol: str) -> None:
        items = self.groups[self.selected_group]
        if symbol in items:
            items.remove(symbol)
            self.save()
            self.changed.emit()

    def move_stock(self, symbol: str, direction: int) -> None:
        items = self.groups[self.selected_group]
        if symbol not in items:
            return
        index = items.index(symbol)
        target = index + direction
        if 0 <= target < len(items):
            items[index], items[target] = items[target], items[index]
            self.save()
            self.changed.emit()

    def create_group(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.groups:
            return False
        self.groups[name] = []
        self.set_group(name)
        return True

    def rename_group(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.groups:
            return False
        self.groups = {name if key == self.selected_group else key: value for key, value in self.groups.items()}
        self.set_group(name)
        return True

    def delete_group(self) -> bool:
        if len(self.groups) == 1:
            return False
        del self.groups[self.selected_group]
        self.set_group(next(iter(self.groups)))
        return True

    def save_position(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        self.save()

    def save(self) -> None:
        remembered = set(self.recent) | {s for items in self.groups.values() for s in items}
        payload = {**self._original, "x": self.x, "y": self.y, "symbol": self.symbol,
                   "recent": self.recent, "groups": self.groups, "selected_group": self.selected_group,
                   "stock_names": {s: [self.stocks[s].name, self.stocks[s].market, self.stocks[s].currency]
                                   for s in remembered if s in self.stocks}}
        try:
            temporary = self.state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.state_path)
        except OSError as error:
            self.storage_error = f"설정 저장 실패: {error}"
        else:
            self.storage_error = ""

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._debounce.stop()
        self.save()
        self.quotes.close()
        self._pool.shutdown(wait=False, cancel_futures=True)

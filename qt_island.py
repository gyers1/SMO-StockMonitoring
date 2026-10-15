from __future__ import annotations

import ctypes
import math
import time
from collections import deque
from typing import Protocol

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QCursor, QKeyEvent, QMouseEvent, QPaintEvent, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QMenu, QWidget

from glass_paint import chevron, magnifier, orb, ribbon_text, star, surface
from qt_dashboard import Dashboard
from qt_model import TickerModel
from qt_market import money

FPS = 120
RIBBON_W, RIBBON_H = 460, 42
DASH_H = 540


class ActiveGuide(Protocol):
    @property
    def card(self) -> QWidget: ...
    index: int


class GlassIsland(QWidget):
    guide_requested = Signal()
    action_completed = Signal(str)

    def __init__(self, model: TickerModel) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.model = model
        self.guide_active: ActiveGuide | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowTitle('SMO · Stock Monitor')
        self.anchor = QPointF(model.x, model.y)
        self.mode = 'orb'
        self.pinned = False
        self.suppressed = False
        self.hover_since = 0.0
        self.left_since = 0.0
        self.press_position: QPointF | None = None
        self.press_anchor = QPointF(self.anchor)
        self.dragged = False
        self.down_before = False
        rect = self.destination('orb')
        self.anchor = rect.topLeft()
        self.values = [rect.x(), rect.y(), rect.width(), rect.height(), .90]
        self.target = list(self.values)
        self.velocity = [0.0] * 5
        self.morphing = False
        self.origin = QPointF()
        self.trim_host(rect)
        self.dashboard = Dashboard(model)
        self.dashboard.setParent(self)
        self.dashboard.back_requested.connect(self.back_to_ribbon)
        self.dashboard.hide()
        self.fade = QGraphicsOpacityEffect(self.dashboard)
        self.dashboard.setGraphicsEffect(self.fade)
        self.fade.setOpacity(0)
        self.fade_started = 0.0
        self.symbols = tuple(model.groups[model.selected_group])
        self.cycle_start = time.perf_counter()
        self.frame_times: deque[float] = deque(maxlen=1000)
        self.last_frame = time.perf_counter()
        self.deadline = self.last_frame
        self.clock = QTimer(self)
        self.clock.setSingleShot(True)
        self.clock.setTimerType(Qt.TimerType.PreciseTimer)
        self.clock.timeout.connect(self.frame)
        self.poller = QTimer(self)
        self.poller.timeout.connect(self.poll_pointer)
        self.poller.start(40)
        model.changed.connect(self.model_changed)
        model.quotes_updated.connect(self.update)
        self.update()

    def show_guide(self) -> None:
        self.guide_requested.emit()

    def destination(self, mode: str) -> QRectF:
        width, height = (36, 36) if mode == 'orb' else (RIBBON_W, DASH_H if mode == 'dashboard' else RIBBON_H)
        screen = QApplication.screenAt(self.anchor.toPoint()) or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        x, y = self.anchor.x(), self.anchor.y()
        if x + width + 10 > area.right():
            x += 36 - width
        if mode == 'dashboard':
            height = min(DASH_H, max(360, area.bottom() - y - 10))
        elif y + height + 10 > area.bottom():
            y += 36 - height
        x = max(area.left() + 10, min(x, area.right() - width - 10))
        y = max(area.top() + 10, min(y, area.bottom() - height - 10))
        return QRectF(x, y, width, height)

    def trim_host(self, rect: QRectF) -> None:
        outer = rect.adjusted(-10, -10, 10, 12).toAlignedRect()
        self.origin = QPointF(outer.topLeft())
        self.setGeometry(outer)

    def body(self) -> QRectF:
        return QRectF(self.values[0] - self.origin.x(), self.values[1] - self.origin.y(), self.values[2], self.values[3])

    def transition(self, mode: str, pinned: bool = False) -> None:
        self.mode, self.pinned = mode, pinned
        self.setToolTip("고정됨 · 돋보기: 시세 · 별: 관심종목" if pinned else "잠깐 보기 · 클릭하여 고정")
        self.dashboard.stop_feedback()
        self.dashboard.hide()
        self.fade_started = 0
        self.hover_since = self.left_since = 0
        destination = self.destination(mode)
        self.target = [destination.x(), destination.y(), destination.width(), destination.height(), .90 if pinned or mode == 'orb' else .70]
        current = QRectF(*self.values[:4])
        outer = current.united(destination).adjusted(-24, -24, 24, 26).toAlignedRect()
        self.origin = QPointF(outer.topLeft())
        self.setGeometry(outer)
        self.morphing = True
        self.cycle_start = time.perf_counter()
        self.start_clock()
        event = self.dashboard.page if mode == 'dashboard' else 'pinned' if pinned else 'preview' if mode == 'ribbon' else 'orb'
        self.action_completed.emit(event)

    def start_clock(self) -> None:
        if not self.clock.isActive():
            self.last_frame = time.perf_counter()
            self.deadline = self.last_frame
            self.clock.start(0)

    def frame(self) -> None:
        now = time.perf_counter()
        self.frame_times.append(now)
        dt = min(.04, max(.0001, now - self.last_frame))
        self.last_frame = now
        if self.morphing:
            steps = max(1, math.ceil(dt / (1 / 240)))
            for _ in range(steps):
                for i in range(5):
                    acceleration = 280 * (self.target[i] - self.values[i]) - 29 * self.velocity[i]
                    self.velocity[i] += acceleration * dt / steps
                    self.values[i] += self.velocity[i] * dt / steps
            self.values[2] = max(32, self.values[2])
            self.values[3] = max(32, self.values[3])
            if self.mode == 'dashboard':
                body = self.body()
                self.dashboard.setGeometry(round(body.x()) + 14, round(body.y()) + 12, RIBBON_W - 28, round(self.target[3]) - 24)
                self.dashboard.setMask(QRegion(0, 0, RIBBON_W - 28, max(1, round(body.height()) - 24)))
                self.fade.setOpacity(min(1.0, max(0.0, (body.height() - RIBBON_H) / 180)))
                self.dashboard.show()
            settled = all(abs(a - b) < (.003 if i == 4 else .15) and abs(self.velocity[i]) < .8
                          for i, (a, b) in enumerate(zip(self.values, self.target)))
            if settled:
                self.values = list(self.target)
                self.velocity = [0.0] * 5
                self.morphing = False
                self.trim_host(QRectF(*self.values[:4]))
                if self.mode == 'dashboard':
                    body = self.body()
                    self.dashboard.setGeometry(round(body.x()) + 14, round(body.y()) + 12, RIBBON_W - 28, round(self.target[3]) - 24)
                    self.dashboard.clearMask()
                    self.fade.setOpacity(1)
                    self.dashboard.show()
        if self.fade_started:
            progress = min(1.0, (now - self.fade_started) / .14)
            self.fade.setOpacity(progress)
            if progress >= 1:
                self.fade_started = 0
        self.update()
        if self.morphing or self.fade_started or (self.mode == 'ribbon' and len(self.symbols) > 1):
            self.deadline += 1 / FPS
            if self.deadline < now:
                self.deadline = now + 1 / FPS
            self.clock.start(max(1, math.ceil((self.deadline - time.perf_counter()) * 1000)))

    def model_changed(self) -> None:
        symbols = tuple(self.model.groups[self.model.selected_group])
        if symbols != self.symbols:
            self.symbols = symbols
            self.cycle_start = time.perf_counter()
        if self.mode == 'ribbon' and len(symbols) > 1:
            self.start_clock()
        self.update()

    def stock_text(self, index: int) -> tuple[str, str, str, bool | None]:
        if not self.symbols:
            return '관심 종목을 추가하세요', '', '', None
        symbol = self.symbols[index % len(self.symbols)]
        stock = self.model.stocks.get(symbol)
        name = stock.name if stock else symbol
        value = self.model.quotes.get(symbol)
        if value is None:
            if not self.model.quotes.configured:
                return name, 'API 설정 필요', '', None
            return name, '조회 실패' if self.model.quotes.error(symbol) else '시세 조회 중…', '', None
        stale = ' · 이전' if self.model.quotes.error(symbol) else ''
        change = f'{value.change_pct:+.2f}%' if value.change_pct is not None else ''
        return name, f'{money(value.price, value.currency)}{stale}', change, value.change_pct > 0 if value.change_pct is not None else None

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = self.body()
        surface(painter, rect, self.values[4])
        if rect.width() < 90:
            orb(painter, rect.center())
            return
        if self.mode == 'dashboard':
            return
        opacity = min(1.0, max(0.0, (rect.width() - 90) / 220))
        painter.setOpacity(opacity)
        magnifier(painter, QPointF(rect.right() - 79, rect.center().y()))
        star(painter, QPointF(rect.right() - 49, rect.center().y()))
        chevron(painter, QPointF(rect.right() - 21, rect.center().y()))
        clip = QRectF(rect.left() + 18, rect.top(), max(1, rect.width() - 128), rect.height())
        painter.save()
        painter.setClipRect(clip.adjusted(0, 3, 0, -3))
        elapsed = max(0.0, time.perf_counter() - self.cycle_start)
        cycle = 4.4
        index = int(elapsed / cycle) % max(1, len(self.symbols))
        phase = elapsed % cycle
        slide = min(1.0, max(0.0, (phase - 3.6) / .8)) if len(self.symbols) > 1 else 0
        slide = slide * slide * (3 - 2 * slide)
        ribbon_text(painter, clip.translated(-slide * (clip.width() + 24), 0), *self.stock_text(index))
        if slide > 0:
            ribbon_text(painter, clip.translated((1 - slide) * (clip.width() + 24), 0), *self.stock_text(index + 1))
        painter.restore()

    def pin_ribbon(self) -> None:
        self.pinned = True
        self.setToolTip("고정됨 · 돋보기: 시세 · 별: 관심종목")
        self.target[4] = .90
        self.morphing = True
        self.start_clock()
        self.action_completed.emit('pinned')

    def open_dashboard(self, page: str) -> None:
        self.dashboard.show_page(page)
        self.transition('dashboard', True)
        self.activateWindow()

    def back_to_ribbon(self) -> None:
        self.transition('ribbon', True)

    def collapse(self) -> None:
        self.suppressed = True
        self.transition('orb')

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            menu.addAction('시세 페이지', lambda: self.open_dashboard('quotes'))
            menu.addAction('관심종목 페이지', lambda: self.open_dashboard('watchlist'))
            menu.addAction('증권사 API 설정', self.dashboard.open_broker_settings)
            menu.addAction('사용 안내 다시 보기', self.show_guide)
            menu.addAction('원으로 접기', self.collapse)
            menu.addSeparator()
            menu.addAction('종료', self.close)
            menu.exec(event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.globalPosition()
            self.press_anchor = QPointF(self.anchor)
            self.dragged = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.press_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition() - self.press_position
            if delta.manhattanLength() > 5:
                self.dragged = True
                change = self.press_anchor + delta - self.anchor
                self.anchor = self.press_anchor + delta
                self.values[0] += change.x()
                self.values[1] += change.y()
                self.target[0] += change.x()
                self.target[1] += change.y()
                self.origin += change
                self.move(self.origin.toPoint())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.mode == 'ribbon' and self.press_position is None:
            distance = self.body().right() - event.position().x()
            tip = '원으로 접기' if distance < 34 else '관심종목 페이지' if distance < 64 else '시세 페이지' if distance < 94 else '고정됨' if self.pinned else '클릭하여 고정'
            if distance >= 94 and self.symbols:
                index = int((time.perf_counter() - self.cycle_start) / 4.4) % len(self.symbols)
                quote = self.model.quotes.get(self.symbols[index])
                if quote is not None:
                    tip += "\n" + quote.tooltip
                    if self.model.quotes.error(self.symbols[index]):
                        tip += "\n갱신 실패 · 마지막으로 받은 가격"
            self.setToolTip(tip)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.press_position = None
        if self.dragged:
            self.model.save_position(round(self.anchor.x()), round(self.anchor.y()))
            return
        rect = self.body()
        position = event.position()
        if self.mode == 'orb':
            self.transition('ribbon', True)
        elif self.mode == 'ribbon':
            original_orb = QRectF(self.anchor.x(), self.anchor.y(), 36, 36)
            if not self.pinned and original_orb.contains(event.globalPosition()):
                self.pin_ribbon()
            elif position.x() > rect.right() - 34:
                self.collapse()
            elif position.x() > rect.right() - 64:
                self.open_dashboard('watchlist')
            elif position.x() > rect.right() - 94:
                self.open_dashboard('quotes')
            else:
                self.pin_ribbon()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.back_to_ribbon() if self.mode == 'dashboard' else self.collapse()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and getattr(self, 'mode', 'orb') == 'dashboard':
            QTimer.singleShot(0, self.poll_pointer)
            if self.guide_active is not None:
                QTimer.singleShot(0, self.guide_active.card.window().raise_)

    def poll_pointer(self) -> None:
        mouse_state = int(ctypes.windll.user32.GetAsyncKeyState(1)) if hasattr(ctypes, 'windll') else 0
        down = bool(mouse_state & 0x8000)
        pressed = (down and not self.down_before) or bool(mouse_state & 1)
        if QApplication.activeModalWidget() or QApplication.activePopupWidget() or self.press_position is not None:
            self.down_before = down
            return
        point = self.mapFromGlobal(QCursor.pos())
        inside = self.body().contains(QPointF(point))
        now = time.perf_counter()
        if not inside:
            self.suppressed = False
            self.hover_since = 0
        if self.guide_active is not None:
            guide = self.guide_active
            over_card = guide.card.rect().contains(guide.card.mapFromGlobal(QCursor.pos()))
            if (over_card and self.mode == 'dashboard') or (self.mode == 'dashboard' and guide.index != 9):
                self.down_before = down
                return
        if self.mode == 'dashboard' and not inside and pressed:
            self.collapse()
        elif self.mode == 'orb' and inside and not self.suppressed and not down and not self.morphing:
            self.hover_since = self.hover_since or now
            if now - self.hover_since >= .2:
                self.transition('ribbon')
        elif self.mode == 'ribbon' and not self.pinned and not self.morphing:
            self.left_since = 0 if inside else (self.left_since or now)
            if not inside and (pressed or now - self.left_since > .5):
                self.collapse()
        self.down_before = down

    def closeEvent(self, event: QCloseEvent) -> None:
        self.clock.stop()
        self.poller.stop()
        self.model.save_position(round(self.anchor.x()), round(self.anchor.y()))
        self.model.close()
        event.accept()
        QApplication.quit()

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from qt_guide_steps import STEPS
from qt_startup import reduced_motion

if TYPE_CHECKING:
    from qt_island import GlassIsland


class Onboarding(QDialog):
    def __init__(self, island: GlassIsland) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.island = island
        self.setWindowTitle('SMO 사용 안내')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self.index = 0
        self.preparing = False
        self.pending = False
        self.started = time.perf_counter()
        self.reduced = reduced_motion()
        self.original = (island.mode, island.pinned, island.dashboard.page)
        self.settings = QSettings(str(island.model.state_path.parent / 'guide.ini'), QSettings.Format.IniFormat)
        self.focus_rect = QRectF()
        self.app_rect = QRectF()
        self.card = QFrame(self)
        self.card.setObjectName('coach')
        self.card.setStyleSheet('''QFrame#coach { background:#192334; border:1px solid #465267; border-radius:20px; }
            QLabel { color:#F5F6F8; background:transparent; border:none; font-size:14px; font-weight:600; }
            QLabel#heading { font-size:17px; font-weight:700; }
            QLabel#progress { color:#B0B3BC; font-size:11px; }
            QLabel#action { color:#E6A16A; font-size:13px; }
            QPushButton { color:#ECEEF2; background:transparent; border:1px solid transparent; border-radius:9px; padding:8px; font-size:12px; }
            QPushButton:hover { background:#293D53; }
            QPushButton:focus { border-color:#E6A16A; }''')
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        top = QHBoxLayout()
        self.progress = QLabel()
        self.progress.setObjectName('progress')
        top.addWidget(self.progress)
        top.addStretch()
        self.skip = QPushButton('안내 건너뛰기')
        self.skip.clicked.connect(self.reject)
        top.addWidget(self.skip)
        layout.addLayout(top)
        self.heading = QLabel()
        self.heading.setObjectName('heading')
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.body = QLabel()
        self.body.setWordWrap(True)
        layout.addWidget(self.body)
        self.action = QLabel()
        self.action.setObjectName('action')
        self.action.setWordWrap(True)
        layout.addWidget(self.action)
        self.card.setFixedWidth(380)
        self.follow = QTimer(self)
        self.follow.setInterval(16)
        self.follow.timeout.connect(self.align_target)
        self.finished.connect(self.restore)
        island.action_completed.connect(self.on_action)
        island.dashboard.stock_selected.connect(self.stock_selected)

    def begin(self) -> None:
        self.island.guide_active = self
        self.show_step()
        self.show()
        self.raise_()
        self.follow.start()

    def stock_selected(self) -> None:
        self.on_action('stock')

    def on_action(self, event: str) -> None:
        if self.preparing or self.pending or event != STEPS[self.index].event:
            return
        self.pending = True
        self.action.setText('잘했어요 · 다음 동작을 살펴볼게요')
        QTimer.singleShot(650, self.advance)

    def advance(self) -> None:
        if not self.isVisible():
            return
        self.pending = False
        if self.index == len(STEPS) - 1:
            self.accept()
        else:
            self.index += 1
            self.show_step()

    def show_step(self) -> None:
        self.preparing = True
        step = STEPS[self.index]
        self.progress.setText(f'직접 해보기  ·  {self.index + 1} / {len(STEPS)}')
        self.heading.setText(step.title)
        self.body.setText(step.body)
        self.action.setText(step.action)
        if self.index == 0:
            self.island.transition('orb')
        self.card.adjustSize()
        self.align_target()
        self.raise_()
        self.preparing = False

    def target_widget(self) -> QWidget | None:
        return {6: self.island.dashboard.entry, 7: self.island.dashboard.back_button}.get(self.index)

    def align_target(self) -> None:
        self.setGeometry(self.island.screen().availableGeometry())
        origin = self.mapFromGlobal(self.island.mapToGlobal(QPoint()))
        self.app_rect = self.island.body().translated(origin)
        widget = self.target_widget()
        if widget is not None:
            self.focus_rect = QRectF(QRect(self.mapFromGlobal(widget.mapToGlobal(QPoint())), widget.size())).adjusted(-5, -5, 5, 5)
            if self.index == 6 and self.island.dashboard.dropdown.isVisible():
                dropdown = self.island.dashboard.dropdown
                self.focus_rect = self.focus_rect.united(QRectF(QRect(self.mapFromGlobal(dropdown.mapToGlobal(QPoint())), dropdown.size())))
        elif self.index in (1, 5, 8):
            offset = {1: 21, 5: 79, 8: 49}[self.index]
            self.focus_rect = QRectF(self.app_rect.right() - offset - 15, self.app_rect.center().y() - 16, 30, 32)
        else:
            self.focus_rect = self.app_rect.adjusted(-3, -3, 3, 3)
        width, height = self.card.width(), self.card.sizeHint().height()
        planned = self.island.destination('dashboard').translated(-self.x(), -self.y())
        x, y = int(planned.left()) - width - 20, int(planned.top())
        if x < 12:
            x = int(planned.right()) + 20
        if x + width > self.width() - 12:
            x = int(planned.center().x() - width / 2)
            y = int(planned.top()) - height - 16
            if y < 12:
                y = int(planned.bottom()) + 16
        self.card.setGeometry(max(12, min(x, self.width() - width - 12)), max(12, min(y, self.height() - height - 12)), width, height)
        radius = 25 if self.index == 9 else 12 if self.index == 6 else min(self.focus_rect.width(), self.focus_rect.height()) / 2
        hole = QPainterPath()
        hole.addRoundedRect(self.focus_rect.adjusted(3, 3, -3, -3), max(0, radius - 3), max(0, radius - 3))
        shaded = QRegion(self.app_rect.adjusted(-6, -6, 6, 6).toAlignedRect()) | QRegion(self.focus_rect.adjusted(-3, -3, 3, 3).toAlignedRect())
        self.setMask((shaded - QRegion(hole.toFillPolygon().toPolygon())) | QRegion(self.card.geometry()))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shade = QPainterPath()
        shade.addRoundedRect(self.app_rect, 22, 22)
        focus = QPainterPath()
        radius = 25 if self.index == 9 else 12 if self.index == 6 else min(self.focus_rect.width(), self.focus_rect.height()) / 2
        focus.addRoundedRect(self.focus_rect, radius, radius)
        painter.fillPath(shade.subtracted(focus), QColor(8, 8, 19, 190))
        alpha = 230 if self.reduced else int(175 + 65 * math.sin((time.perf_counter() - self.started) * math.tau / 1.8))
        painter.setPen(QPen(QColor(230, 161, 106, alpha), 2.5))
        painter.drawPath(focus)

    def restore(self, result: int) -> None:
        self.follow.stop()
        self.island.guide_active = None
        self.island.action_completed.disconnect(self.on_action)
        self.island.dashboard.stock_selected.disconnect(self.stock_selected)
        self.settings.setValue('completed', True)
        self.settings.sync()
        self.island.suppressed = True
        if result == QDialog.DialogCode.Accepted:
            QTimer.singleShot(250, self.island.dashboard.open_broker_settings)
        else:
            self.island.collapse()
        self.deleteLater()


def show_guide(island: GlassIsland) -> None:
    if island.guide_active is not None:
        return
    guide = Onboarding(island)
    guide.begin()

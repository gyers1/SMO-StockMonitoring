from __future__ import annotations

import ctypes
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from glass_paint import orb, surface


def reduced_motion() -> bool:
    enabled = ctypes.c_int(1)
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)) and not enabled.value


def smooth(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


class StartupSplash(QWidget):
    finished = Signal()

    def __init__(self, destination: QPointF) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('SMO 시작')
        arrival = destination + QPointF(18, 18)
        center = arrival
        bounds = QRectF(center.x() - 170, center.y() - 160, 340, 270).united(QRectF(arrival.x() - 65, arrival.y() - 65, 130, 130))
        self.setGeometry(bounds.toAlignedRect())
        self.center = center - QPointF(self.pos())
        self.destination = arrival - QPointF(self.pos())
        self.started = time.perf_counter()
        self.reduced = reduced_motion()
        self.duration = .2 if self.reduced else 1.65
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(8)

    def tick(self) -> None:
        if time.perf_counter() - self.started >= self.duration:
            self.timer.stop()
            self.close()
            self.finished.emit()
            self.deleteLater()
        else:
            self.update()

    def pose(self, progress: float) -> tuple[QPointF, float, float]:
        if self.reduced:
            return self.destination, 36.0, 1.0
        if progress < .42:
            y = 38 - 128 * smooth(progress / .42)
        elif progress < .72:
            y = -90 + 100 * smooth((progress - .42) / .30)
        elif progress < .88:
            y = 10 - 20 * smooth((progress - .72) / .16)
        else:
            y = -10 + 10 * smooth((progress - .88) / .12)
        size = 88 - 52 * smooth((progress - .25) / .75)
        position = self.center + QPointF(0, y)
        return position, size, smooth(progress / .18)

    def paintEvent(self, event: QPaintEvent) -> None:
        progress = min(1.0, (time.perf_counter() - self.started) / self.duration)
        position, size, opacity = self.pose(progress)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.reduced:
            for delay in (0.0, .12):
                wave = max(0.0, min(1.0, (progress - delay) / .8))
                alpha = round(62 * math.sin(math.pi * wave) * (1 - wave))
                painter.setPen(QPen(QColor(160, 189, 219, alpha), 1.2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.center + QPointF(0, 34), 35 + 120 * wave, 5 + 12 * wave)
        painter.setOpacity(opacity)
        surface(painter, QRectF(position.x() - size / 2, position.y() - size / 2, size, size), .94)
        painter.translate(position)
        painter.scale(size / 36, size / 36)
        orb(painter, QPointF())

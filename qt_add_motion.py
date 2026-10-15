from __future__ import annotations

import math
import time

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget


class AddMotion(QLabel):
    finished = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance)
        self.origin = QRect()
        self.target = QRect()
        self.started = 0.0
        self.hide()

    def start(self, snapshot: QPixmap, origin: QRect, target: QRect) -> None:
        self.timer.stop()
        self.setPixmap(snapshot)
        self.setScaledContents(True)
        self.origin, self.target = origin, target
        self.started = time.perf_counter()
        self.setGeometry(origin)
        self.show()
        self.raise_()
        self.timer.start(8)

    def advance(self) -> None:
        elapsed = time.perf_counter() - self.started
        if elapsed >= 0.56:
            self.stop()
            return
        progress = 1 - math.exp(-10 * elapsed) * (math.cos(11 * elapsed) + 0.35 * math.sin(11 * elapsed))
        x = round(self.origin.x() + (self.target.x() - self.origin.x()) * progress)
        y = round(self.origin.y() + (self.target.y() - self.origin.y()) * progress)
        width = round(self.origin.width() + (self.target.width() - self.origin.width()) * progress)
        height = round(self.origin.height() + (self.target.height() - self.origin.height()) * progress)
        self.setGeometry(x, y, max(1, width), max(1, height))
        next_frame = (math.floor(elapsed * 120) + 1) / 120
        self.timer.start(max(1, math.ceil((next_frame - elapsed) * 1000)))

    def stop(self) -> None:
        self.timer.stop()
        self.hide()
        self.finished.emit()

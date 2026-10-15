from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen

TEXT = QColor('#ECEEF2')
MUTED = QColor('#B0B3BC')
FROZEN = QColor('#A0BDDB')
ORANGE = QColor('#E6A16A')


def surface(painter: QPainter, rect: QRectF, opacity: float) -> None:
    radius = min(24.0, rect.height() / 2)
    painter.setPen(Qt.PenStyle.NoPen)
    for spread in range(9, 0, -1):
        painter.setBrush(QColor(0, 0, 8, 3 + (9 - spread)))
        painter.drawRoundedRect(rect.adjusted(-spread, -spread + 2, spread, spread + 2), radius + spread, radius + spread)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0, QColor(31, 40, 57, round(255 * opacity)))
    gradient.setColorAt(.45, QColor(14, 17, 31, round(255 * opacity)))
    gradient.setColorAt(1, QColor(8, 8, 19, round(255 * opacity)))
    painter.setBrush(gradient)
    painter.drawRoundedRect(rect, radius, radius)
    rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    rim.setColorAt(0, QColor(195, 217, 240, 125))
    rim.setColorAt(.4, QColor(160, 189, 219, 38))
    rim.setColorAt(1, QColor(160, 189, 219, 60))
    painter.setPen(QPen(rim, .8))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), radius, radius)
    painter.setPen(QPen(QColor(255, 255, 255, 12), .6))
    painter.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), radius - 1, radius - 1)


def star(painter: QPainter, center: QPointF, active: bool = False) -> None:
    path = QPainterPath()
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = 7.4 if i % 2 == 0 else 3.7
        point = center + QPointF(math.cos(angle) * radius, math.sin(angle) * radius)
        if i == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    painter.setPen(QPen(ORANGE if active else TEXT, 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QColor(230, 161, 106, 35) if active else Qt.BrushStyle.NoBrush)
    painter.drawPath(path)


def magnifier(painter: QPainter, center: QPointF) -> None:
    painter.setPen(QPen(TEXT, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center + QPointF(-1.5, -1.5), 5.2, 5.2)
    painter.drawLine(center + QPointF(2.5, 2.5), center + QPointF(6.5, 6.5))


def chevron(painter: QPainter, center: QPointF) -> None:
    painter.setPen(QPen(MUTED, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    path = QPainterPath(center + QPointF(2, -4))
    path.lineTo(center + QPointF(-2, 0))
    path.lineTo(center + QPointF(2, 4))
    painter.drawPath(path)


def orb(painter: QPainter, center: QPointF) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    for x, height, color in ((-6, 6, FROZEN), (0, 12, TEXT), (6, 9, ORANGE)):
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(center.x() + x - 1.2, center.y() - height / 2, 2.4, height), 1.2, 1.2)


def ribbon_text(painter: QPainter, rect: QRectF, name: str, price: str, change: str, rising: bool | None) -> None:
    font = QFont('Pretendard', 10)
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(TEXT)
    name_width = min(114, rect.width() * .34)
    label = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, int(name_width))
    painter.drawText(QRectF(rect.x(), rect.y(), name_width, rect.height()), Qt.AlignmentFlag.AlignVCenter, label)
    font.setWeight(QFont.Weight.Normal)
    painter.setFont(font)
    price_rect = QRectF(rect.x() + name_width + 9, rect.y(), rect.width() - name_width - 9, rect.height())
    change_width = painter.fontMetrics().horizontalAdvance(change) + 12 if change else 0
    price_rect.setWidth(max(0, price_rect.width() - change_width))
    price = painter.fontMetrics().elidedText(price, Qt.TextElideMode.ElideRight, int(price_rect.width()))
    painter.drawText(price_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, price)
    if change:
        painter.setPen(ORANGE if rising else FROZEN)
        painter.drawText(QRectF(rect.right() - change_width + 8, rect.y(), change_width - 8, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, change)

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPointF, QSettings, Qt
from PySide6.QtGui import QColor, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from glass_paint import orb

if TYPE_CHECKING:
    from qt_island import GlassIsland


def claim_first_guide(path: Path) -> bool:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    seen = settings.value('shown', False, type=bool) or settings.value('completed', False, type=bool)
    settings.setValue('shown', True)
    settings.sync()
    return not seen


def server_name(directory: Path) -> str:
    digest = hashlib.sha256(str(directory.resolve()).casefold().encode()).hexdigest()[:20]
    return 'SMO-' + digest


def restore_running_app(directory: Path) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(server_name(directory))
    if not socket.waitForConnected(700):
        return False
    socket.write(b'show')
    socket.waitForBytesWritten(700)
    socket.disconnectFromServer()
    return True


class AppPresence(QObject):
    """Own the persistent tray and restore the floating window without restarting."""

    def __init__(self, window: GlassIsland) -> None:
        super().__init__(window)
        self.window = window
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#080813'))
        painter.drawEllipse(1, 1, 30, 30)
        orb(painter, QPointF(16, 16))
        painter.end()
        icon = QIcon(pixmap)
        window.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip('SMO · 클릭하여 다시 보기')
        self.menu = QMenu()
        self.menu.addAction('SMO 다시 보기', self.restore)
        self.menu.addAction('시세', lambda: self.open_page('quotes'))
        self.menu.addAction('관심종목', lambda: self.open_page('watchlist'))
        self.menu.addAction('설정', self.open_settings)
        self.menu.addSeparator()
        self.menu.addAction('종료', QApplication.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.activated)
        self.tray.show()
        window.installEventFilter(self)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            window.setWindowFlag(Qt.WindowType.Tool, False)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self.receive)
        self.server.listen(server_name(window.model.state_path.parent))
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore()

    def receive(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is not None:
                socket.close()
                socket.deleteLater()
                self.restore()

    def restore(self) -> None:
        window = self.window
        screen = QApplication.screenAt(window.anchor.toPoint())
        if screen is None:
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            if screen is not None:
                window.anchor = QPointF(screen.availableGeometry().center()) - QPointF(18, 18)
        if window.guide_active is None:
            rect = window.destination('orb')
            window.anchor = rect.topLeft()
            window.values = [rect.x(), rect.y(), rect.width(), rect.height(), .90]
            window.velocity = [0.0] * 5
            window.trim_host(rect)
            window.suppressed = True
            window.transition('orb')
        window.showNormal()
        window.raise_()
        window.activateWindow()
        window.poller.start(40)
        if window.guide_active is not None:
            window.guide_active.card.window().raise_()

    def open_page(self, page: str) -> None:
        self.restore()
        self.window.open_dashboard(page)

    def open_settings(self) -> None:
        self.restore()
        self.window.dashboard.open_broker_settings()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.window and event.type() == QEvent.Type.Close and QSystemTrayIcon.isSystemTrayAvailable():
            if self.window.guide_active is not None:
                self.window.guide_active.card.window().close()
            self.window.dashboard.stop_feedback()
            self.window.clock.stop()
            self.window.poller.stop()
            self.window.model.save_position(round(self.window.anchor.x()), round(self.window.anchor.y()))
            self.window.hide()
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    def shutdown(self) -> None:
        self.tray.hide()
        self.server.close()
        self.window.clock.stop()
        self.window.poller.stop()
        self.window.model.save_position(round(self.window.anchor.x()), round(self.window.anchor.y()))
        self.window.model.close()

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent

from PySide6.QtCore import QLockFile, QPointF, QSettings, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from qt_island import GlassIsland
from qt_onboarding import show_guide
from qt_model import TickerModel
from qt_startup import StartupSplash
from app_version import VERSION
from app_paths import DATA_DIR


def configure_fonts(app: QApplication) -> None:
    for path in (ROOT / 'assets' / 'fonts').glob('*.ttf'):
        QFontDatabase.addApplicationFont(str(path))
    font = QFont('Pretendard', 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet('QToolTip, QMenu { background:#192334; color:#ECEEF2; border:1px solid #354456; padding:5px; }')


def run() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SMO")
    app.setApplicationVersion(VERSION)
    lock = QLockFile(str(DATA_DIR / "SMO.lock"))
    if not lock.tryLock(100):
        return
    configure_fonts(app)
    model = TickerModel()
    if not model.state_path.exists():
        center = app.primaryScreen().availableGeometry().center()
        model.x, model.y = center.x() - 18, center.y() - 18
    window = GlassIsland(model)
    window.guide_requested.connect(partial(show_guide, window))
    guide = QSettings(str(DATA_DIR / "guide.ini"), QSettings.Format.IniFormat)
    splash = StartupSplash(QPointF(window.anchor))

    def ready() -> None:
        window.show()
        window.suppressed = True
        if '--guide' in sys.argv or not guide.value("completed", False, type=bool):
            QTimer.singleShot(250, window.show_guide)
        from qt_update import startup_check
        startup_check(window, window.dashboard.status)

    splash.finished.connect(ready)
    splash.show()
    app.exec()


if __name__ == '__main__':
    run()

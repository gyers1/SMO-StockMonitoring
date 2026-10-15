from __future__ import annotations

import sys
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app_paths import DATA_DIR
from app_version import VERSION
from qt_styles import STYLE
from update_service import Release, UpdateError, check_release, download_release, is_newer
from update_install import install_and_restart



class UpdateDialog(QDialog):
    progress_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('SMO 업데이트')
        self.setFixedWidth(400)
        self.setStyleSheet(STYLE)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending: Future[Release | None] | Future[Path] | None = None
        self.release: Release | None = None
        self.downloading = False
        self.cancel = Event()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        title = QLabel(f'SMO {VERSION}')
        title.setObjectName('title')
        layout.addWidget(title)
        self.status = QLabel('새 버전을 확인하고 있어요…')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#E6A16A; background:#241E1B; padding:12px; border-radius:10px; font-weight:600;')
        layout.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setStyleSheet('QProgressBar {background:#192334; border:0; border-radius:4px; text-align:center; height:22px;} QProgressBar::chunk {background:#D99560; border-radius:3px;}')
        self.bar.hide()
        layout.addWidget(self.bar)
        self.progress_changed.connect(self.bar.setValue)
        self.action = QPushButton('다시 확인')
        self.action.clicked.connect(self.act)
        layout.addWidget(self.action)
        close = QPushButton('닫기')
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)
        self.finished.connect(self.cleanup)
        self.check()

    def check(self) -> None:
        self.release = None
        self.action.setEnabled(False)
        self.status.setText('새 버전을 확인하고 있어요…')
        self.pending = self.pool.submit(check_release)
        self.timer.start()

    def act(self) -> None:
        if self.release is None:
            self.check()
            return
        self.downloading = True
        self.bar.show()
        self.action.setEnabled(False)
        self.status.setText('다운로드 중 · 확인이 끝나면 앱을 다시 시작해요.')
        self.pending = self.pool.submit(download_release, self.release, DATA_DIR / 'updates', self.progress_changed.emit, self.cancel)
        self.timer.start()

    def poll(self) -> None:
        if self.pending is None or not self.pending.done():
            return
        pending, self.pending = self.pending, None
        self.timer.stop()
        try:
            result = pending.result()
            if isinstance(result, Path):
                self.status.setText('100% · 파일 확인 완료. 업데이트 후 다시 시작합니다.')
                QTimer.singleShot(500, lambda: self.install(result))
                return
            self.release = result if result is not None and is_newer(result) else None
            self.status.setText('아직 공개된 업데이트가 없습니다.' if result is None else '최신 버전을 사용하고 있어요.' if self.release is None else f'{result.tag_name} 업데이트가 준비됐어요.')
            frozen = bool(getattr(sys, 'frozen', False))
            self.action.setText('다운로드 · 재시작' if self.release else '다시 확인')
            self.action.setEnabled(self.release is None or frozen)
            if self.release and not frozen:
                self.status.setText(self.status.text() + '\n개발 실행에서는 설치하지 않습니다.')
        except UpdateError as error:
            self.release = None
            self.downloading = False
            self.status.setText(str(error))
            self.action.setText('다시 확인')
            self.action.setEnabled(True)

    def install(self, installer: Path) -> None:
        if self.cancel.is_set():
            return
        try:
            install_and_restart(installer)
        except (UpdateError, OSError):
            self.status.setText('업데이트를 시작하지 못했습니다. 다시 확인해 주세요.')
            self.downloading = False
            self.action.setEnabled(True)
            return
        QApplication.closeAllWindows()
        QApplication.quit()

    def cleanup(self) -> None:
        self.cancel.set()
        self.timer.stop()
        self.pool.shutdown(wait=False, cancel_futures=True)


class StartupCheck(QObject):
    def __init__(self, window: QWidget, status: QLabel) -> None:
        super().__init__(window)
        self.status = status
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pending = self.pool.submit(check_release)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def poll(self) -> None:
        if not self.pending.done():
            return
        self.timer.stop()
        try:
            release = self.pending.result()
            if release is not None and is_newer(release):
                self.status.setText('새 버전이 있어요 · 설정에서 업데이트하세요')
        except UpdateError:
            pass
        self.pool.shutdown(wait=False)
        self.deleteLater()


def startup_check(window: QWidget, status: QLabel) -> None:
    StartupCheck(window, status)

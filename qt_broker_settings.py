from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from broker_settings import BrokerCredentials, BrokerSettings, SettingsError
from qt_styles import STYLE
from quote_service import ConnectionResult, check_connection


class BrokerSettingsDialog(QDialog):
    applied = Signal()
    guide_requested = Signal()

    def __init__(self, store: BrokerSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle('SMO 설정')
        self.setModal(True)
        self.setFixedWidth(420)
        self.setStyleSheet(STYLE)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='api-check')
        self.pending: Future[ConnectionResult] | None = None
        self.save_after_probe = False
        self.probing_credentials: BrokerCredentials | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        title = QLabel('설정')
        title.setObjectName('title')
        root.addWidget(title)
        intro = QLabel('본인 명의 API 키로 시세만 조회합니다.')
        root.addWidget(intro)
        broker_row = QHBoxLayout()
        self.provider = QComboBox()
        self.provider.addItem('토스증권', 'toss')
        self.provider.addItem('키움증권', 'kiwoom')
        self.provider.addItem('미래에셋증권', 'mirae')
        self.provider.addItem('한국투자증권', 'kis')
        broker_row.addWidget(self.provider, 1)
        self.issue = QPushButton('발급 안내 ↗')
        self.issue.setAccessibleName('선택한 증권사의 공식 API 발급 안내 열기')
        self.issue.clicked.connect(self.open_issue)
        broker_row.addWidget(self.issue)
        root.addLayout(broker_row)
        self.support = QLabel()
        self.support.setWordWrap(True)
        root.addWidget(self.support)
        self.key_label = QLabel('Client ID')
        self.key = QLineEdit()
        self.secret_label = QLabel('Client Secret')
        self.secret = QLineEdit()
        for label, entry in ((self.key_label, self.key), (self.secret_label, self.secret)):
            label.setBuddy(entry)
            entry.setEchoMode(QLineEdit.EchoMode.Password)
            entry.setMaxLength(4096)
            root.addWidget(label)
            root.addWidget(entry)
        self.show_keys = QCheckBox('입력한 키 표시')
        self.show_keys.toggled.connect(self.toggle_keys)
        root.addWidget(self.show_keys)
        note = QLabel('현재 Windows 계정에 암호화하여 저장합니다.\n연결 확인은 인증 요청을 보내며, 저장하면 시세 조회를 시작합니다.')
        note.setWordWrap(True)
        note.setObjectName('muted')
        root.addWidget(note)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#E6A16A; font-size:13px; font-weight:600; padding:8px; background:#241E1B; border-radius:8px;')
        root.addWidget(self.status)
        actions = QHBoxLayout()
        self.delete_button = QPushButton('연결 해제')
        self.delete_button.clicked.connect(self.clear_settings)
        self.probe_button = QPushButton('연결 확인')
        self.probe_button.clicked.connect(self.probe)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        actions.addWidget(self.probe_button)
        root.addLayout(actions)
        buttons = QHBoxLayout()
        cancel = QPushButton('닫기')
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton('저장')
        self.save_button.setStyleSheet('background: #293D53; font-weight: 700; padding: 9px 12px;')
        self.save_button.clicked.connect(self.save_settings)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button, 1)
        root.addLayout(buttons)
        update_button = QPushButton('업데이트')
        update_button.clicked.connect(self.open_updates)
        root.addWidget(update_button)
        self.guide_button = QPushButton('사용 안내')
        self.guide_button.clicked.connect(self.open_guide)
        root.addWidget(self.guide_button)
        self.provider.currentIndexChanged.connect(self.select_provider)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll_probe)
        self.finished.connect(self.finish_dialog)
        self.select_provider()
        try:
            stored = self.store.load()
            if stored is not None:
                self.provider.setCurrentIndex(self.provider.findData(stored.provider))
                self.key.setText(stored.key)
                self.secret.setText(stored.secret)
                self.status.setText('저장된 연결 정보를 불러왔습니다.')
        except SettingsError as error:
            self.status.setText(str(error))

    def open_guide(self) -> None:
        self.reject()
        self.guide_requested.emit()

    def select_provider(self) -> None:
        self.key.clear()
        self.secret.clear()
        self.show_keys.setChecked(False)
        self.status.clear()
        supported = self.provider.currentData() != 'mirae'
        for widget in (self.key, self.secret, self.show_keys, self.probe_button, self.save_button):
            widget.setEnabled(supported)
        match self.provider.currentData():
            case 'toss':
                labels = ('Client ID', 'Client Secret')
                info = '국내·미국 시세 · 계정의 API 이용 및 시세 권한이 필요합니다.'
                url = 'https://home.tossinvest.com/ko/open-api'
            case 'kiwoom':
                labels = ('App Key', 'Secret Key')
                info = '키움 REST API · 국내·미국 시세 · API 이용 신청이 필요합니다.'
                url = 'https://openapi.kiwoom.com/intro/serviceInfo'
            case 'kis':
                labels = ('App Key', 'App Secret')
                info = '실전용 키 · 국내·미국 시세 · 5초 간격 조회\n미국 시세는 이용 권한에 따라 지연될 수 있습니다.'
                url = 'https://apiportal.koreainvestment.com/about-howto'
            case _:
                labels = ('API 키', 'API 비밀 키')
                info = 'SMO 연결 준비 중 · 별도 모듈 연동 필요'
                url = 'https://securities.miraeasset.com/imf/200/imf401.do'
        self.key_label.setText(labels[0])
        self.secret_label.setText(labels[1])
        self.support.setText(info)
        self.issue.setText('발급 안내 ↗' if supported else '공식 안내 ↗')
        self.issue.setToolTip(url)

    def open_issue(self) -> None:
        QDesktopServices.openUrl(QUrl(self.issue.toolTip()))

    def toggle_keys(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.key.setEchoMode(mode)
        self.secret.setEchoMode(mode)

    def credentials(self) -> BrokerCredentials | None:
        if self.provider.currentData() == 'mirae':
            return None
        if not self.key.text().strip() or not self.secret.text().strip():
            self.status.setText('API 키 두 항목을 모두 입력해 주세요.')
            return None
        return BrokerCredentials(str(self.provider.currentData()), self.key.text().strip(), self.secret.text().strip())

    def open_updates(self) -> None:
        from qt_update import UpdateDialog
        dialog = UpdateDialog(self)
        dialog.exec()

    def save_settings(self) -> None:
        self.start_probe(save=True)

    def clear_settings(self) -> None:
        try:
            self.store.clear()
        except SettingsError as error:
            self.status.setText(str(error))
            return
        self.key.clear()
        self.secret.clear()
        self.applied.emit()
        self.status.setText('저장된 연결 정보를 삭제했습니다. 시세 조회가 중지됩니다.')

    def probe(self) -> None:
        self.start_probe(save=False)

    def start_probe(self, *, save: bool) -> None:
        credentials = self.credentials()
        if credentials is None or self.pending is not None:
            return
        self.save_after_probe = save
        self.probing_credentials = credentials
        self.pending = self.pool.submit(check_connection, credentials.provider, credentials.key, credentials.secret)
        for widget in (self.provider, self.key, self.secret, self.save_button, self.delete_button, self.probe_button):
            widget.setEnabled(False)
        self.status.setText('연결 확인 중… 성공하면 암호화하여 저장합니다.' if save else '증권사 연결을 확인하고 있습니다…')
        self.timer.start()

    def poll_probe(self) -> None:
        if self.pending is None or not self.pending.done():
            return
        result = self.pending.result()
        self.pending = None
        self.timer.stop()
        self.status.setText(result.message)
        if result.success and self.save_after_probe and self.probing_credentials is not None:
            try:
                self.store.save(self.probing_credentials)
            except SettingsError as error:
                self.status.setText(str(error))
            else:
                self.applied.emit()
                self.status.setText('연결 확인·저장 완료\n시세를 불러오고 있어요. 이제 닫아도 됩니다.')
        elif self.save_after_probe:
            self.status.setText('연결하지 못해 저장하지 않았어요.\n' + result.message)
        self.probing_credentials = None
        for widget in (self.provider, self.key, self.secret, self.save_button, self.delete_button, self.probe_button):
            widget.setEnabled(True)

    def finish_dialog(self) -> None:
        self.timer.stop()
        if self.pending is not None:
            self.pending.cancel()
        self.pending = None
        self.probing_credentials = None
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.key.clear()
        self.secret.clear()

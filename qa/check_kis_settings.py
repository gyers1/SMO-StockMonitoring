from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from broker_settings import BrokerCredentials, BrokerSettings
from qt_app import configure_fonts
from qt_broker_settings import BrokerSettingsDialog
from quote_service import ConnectionResult

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
configure_fonts(app)
with TemporaryDirectory() as temporary:
    store = BrokerSettings(Path(temporary) / 'credentials.json')
    dialog = BrokerSettingsDialog(store)
    dialog.show()
    dialog.provider.setCurrentIndex(dialog.provider.findData('kis'))
    app.processEvents()
    assert dialog.key_label.text() == 'App Key'
    assert dialog.secret_label.text() == 'App Secret'
    assert dialog.key.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.save_button.isEnabled()
    with patch('qt_broker_settings.QDesktopServices.openUrl') as opened:
        QTest.mouseClick(dialog.issue, Qt.MouseButton.LeftButton)
        assert opened.call_args.args[0].toString() == 'https://apiportal.koreainvestment.com/about-howto'
    QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert store.load() is None
    dialog.key.setText('fixture-kis-key')
    dialog.secret.setText('fixture-kis-secret')
    with patch('qt_broker_settings.check_connection', return_value=ConnectionResult(True, '한국투자증권 연결 확인 · 국내 시세 조회 성공 (미국 시세 권한은 별도 확인)')) as probe:
        QTest.mouseClick(dialog.probe_button, Qt.MouseButton.LeftButton)
        deadline = time.monotonic() + 3
        while dialog.pending is not None and time.monotonic() < deadline:
            app.processEvents()
        assert dialog.pending is None
        probe.assert_called_once_with('kis', 'fixture-kis-key', 'fixture-kis-secret')
    assert dialog.grab().save('qa/kis-settings.png')
    with patch('qt_broker_settings.check_connection', return_value=ConnectionResult(True, 'fixture success')):
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        QTest.qWait(300)
    assert store.load() == BrokerCredentials('kis', 'fixture-kis-key', 'fixture-kis-secret')
    assert 'fixture-kis' not in store.path.read_text()
    reopened = BrokerSettingsDialog(store)
    reopened.show()
    app.processEvents()
    assert reopened.provider.currentData() == 'kis'
    assert reopened.key.text() == 'fixture-kis-key'
    assert reopened.grab().save('qa/kis-restored.png')
    reopened.provider.setCurrentIndex(reopened.provider.findData('toss'))
    assert reopened.key.text() == reopened.secret.text() == ''
    reopened.reject()
print('KIS native settings: save, DPAPI, restore, masking, required fields, provider switch, official link, simulated probe PASS')

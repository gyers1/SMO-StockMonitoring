from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import json
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from broker_settings import BrokerCredentials, BrokerSettings, SettingsError
from qt_app import configure_fonts
from qt_broker_settings import BrokerSettingsDialog
from quote_service import ConnectionResult
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

app = QApplication([])
configure_fonts(app)
with TemporaryDirectory() as directory:
    store = BrokerSettings(Path(directory) / 'credential.json')
    credentials = BrokerCredentials('toss', 'qa-not-real-key', 'qa-not-real-secret')
    assert store.load() is None
    store.save(credentials)
    assert store.load() == credentials
    assert 'qa-not-real' not in store.path.read_text()
    assert credentials.key not in repr(credentials)
    altered = json.loads(store.path.read_text())
    altered['provider'] = 'kiwoom'
    store.path.write_text(json.dumps(altered))
    try:
        store.load()
    except SettingsError:
        pass
    else:
        raise AssertionError('provider substitution accepted')
    store.save(credentials)
    dialog = BrokerSettingsDialog(store)
    dialog.show()
    QTest.qWait(100)
    assert dialog.key.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.key.text() == credentials.key
    dialog.grab().save('qa/broker-settings.png')
    dialog.key.setText('cancelled-change')
    dialog.reject()
    assert store.load() == credentials
    dialog = BrokerSettingsDialog(store)
    dialog.show()
    dialog.provider.setCurrentIndex(2)
    assert not dialog.save_button.isEnabled()
    assert not dialog.key.isEnabled()
    QTest.qWait(100)
    dialog.grab().save('qa/broker-mirae.png')
    dialog.provider.setCurrentIndex(1)
    QTest.qWait(100)
    dialog.grab().save('qa/broker-kiwoom.png')
    dialog.key.setText('qa-kiwoom-key')
    dialog.secret.setText('qa-kiwoom-secret')
    with patch('qt_broker_settings.check_connection', return_value=ConnectionResult(True, 'QA 인증 응답')):
        QTest.mouseClick(dialog.probe_button, Qt.MouseButton.LeftButton)
        assert not dialog.provider.isEnabled()
        assert not dialog.save_button.isEnabled()
        QTest.qWait(200)
        assert dialog.pending is None
        assert dialog.provider.isEnabled()
        assert dialog.status.text() == 'QA 인증 응답'
    with patch('qt_broker_settings.check_connection', return_value=ConnectionResult(True, 'fixture success')):
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        QTest.qWait(300)
    assert store.load() == BrokerCredentials('kiwoom', 'qa-kiwoom-key', 'qa-kiwoom-secret')
    dialog = BrokerSettingsDialog(store)
    dialog.clear_settings()
    assert store.load() is None
    dialog.reject()
    store.path.write_text('{"provider":"toss","encrypted":"tampered"}')
    try:
        store.load()
    except SettingsError:
        pass
    else:
        raise AssertionError('corrupt settings accepted')
print('DPAPI roundtrip, no plaintext, masking, cancel, save, clear, unsupported and corruption PASS')

from __future__ import annotations
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from threading import Event
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from qt_app import configure_fonts
from qt_model import TickerModel
from qt_island import GlassIsland
from qt_onboarding import Onboarding
from qt_startup import StartupSplash
from qt_broker_settings import BrokerSettingsDialog
from qt_update import UpdateDialog
from update_service import Release, UpdateError
from quote_service import ConnectionResult

app=QApplication([])
app.setQuitOnLastWindowClosed(False)
configure_fonts(app)
output=ROOT/'qa/revision'
output.mkdir(exist_ok=True)
backdrop=QWidget(None, Qt.WindowType.WindowStaysOnTopHint)
backdrop.setStyleSheet('background:#303541;')
backdrop.showMaximized()
QTest.qWait(200)

def capture(guide, name):
    QTest.qWait(300)
    area=guide.app_rect.toAlignedRect().united(guide.card.geometry()).adjusted(-10,-10,10,10)
    point=guide.mapToGlobal(area.topLeft())
    guide.screen().grabWindow(0,point.x(),point.y(),area.width(),area.height()).save(str(output/name))

with tempfile.TemporaryDirectory(prefix='SMO-revision-') as temp:
    model=TickerModel(Path(temp)/'ticker_state.json')
    center=app.primaryScreen().availableGeometry().center()
    model.x,model.y=center.x()+142,center.y()+62
    island=GlassIsland(model)
    splash=StartupSplash(QPointF(island.anchor))
    splash.show()
    for number, delay in enumerate((200,500,600)):
        QTest.qWait(delay)
        point=splash.pos()
        splash.screen().grabWindow(0,point.x(),point.y(),splash.width(),splash.height()).save(str(output/f'startup-{number}.png'))
    QTest.qWait(450)
    island.show()
    QTest.qWait(200)
    island.grab().save(str(output/'startup-final.png'))
    guide=Onboarding(island)
    guide.begin()
    QCursor.setPos(10,10)
    QTest.qWait(800)
    def click(offset=None):
        rect=island.body()
        point=rect.center().toPoint() if offset is None else QPoint(int(rect.right()-offset),int(rect.center().y()))
        QTest.mouseClick(island,Qt.MouseButton.LeftButton,pos=point)
        QTest.qWait(1100)
    for index in range(10):
        assert guide.index==index,(index,guide.index,island.mode)
        capture(guide,f'guide-{index}.png')
        if index in (0,4): click()
        elif index==1: click(21)
        elif index==2:
            QCursor.setPos(island.mapToGlobal(island.body().center().toPoint()))
            QTest.qWait(1400)
        elif index==3:
            QCursor.setPos(guide.card.mapToGlobal(guide.card.rect().center()))
            QTest.qWait(1400)
        elif index==5: click(79)
        elif index==6:
            island.dashboard.entry.setFocus()
            island.dashboard.entry.setText('\uC0BC')
            QTest.qWait(600)
            assert island.dashboard.dropdown.rows
            capture(guide,'search.png')
            QTest.mouseClick(island.dashboard.dropdown.rows[0],Qt.MouseButton.LeftButton)
            QTest.qWait(1100)
        elif index==7:
            QTest.mouseClick(island.dashboard.back_button,Qt.MouseButton.LeftButton)
            QTest.qWait(1100)
        elif index==8: click(49)
        else:
            def close_settings():
                modal=QApplication.activeModalWidget()
                assert isinstance(modal,BrokerSettingsDialog)
                modal.grab().save(str(output/'settings.png'))
                modal.reject()
            QTimer.singleShot(1600,close_settings)
            QCursor.setPos(10,10)
            with patch('qt_island.ctypes.windll.user32.GetAsyncKeyState',return_value=1): island.poll_pointer()
            QTest.qWait(2000)
    assert island.guide_active is None
    dialog=BrokerSettingsDialog(model.broker_settings)
    dialog.show()
    dialog.key.setText('fixture');dialog.secret.setText('fixture')
    with patch('qt_broker_settings.check_connection',return_value=ConnectionResult(True,'ok')):
        QTest.mouseClick(dialog.save_button,Qt.MouseButton.LeftButton)
        QTest.qWait(400)
    assert model.broker_settings.load() is not None
    dialog.grab().save(str(output/'settings-success.png'))
    with patch('qt_broker_settings.check_connection',return_value=ConnectionResult(False,'fixture failure')):
        QTest.mouseClick(dialog.save_button,Qt.MouseButton.LeftButton)
        QTest.qWait(400)
    dialog.grab().save(str(output/'settings-failed.png'))
    dialog.provider.setCurrentIndex(2)
    QTest.qWait(300)
    dialog.grab().save(str(output/'settings-mirae.png'))
    dialog.reject()
    with patch('qt_update.check_release',return_value=None):
        update=UpdateDialog()
        update.show();QTest.qWait(400)
        update.grab().save(str(output/'update.png'))
        update.reject()
    with patch('qt_update.check_release',return_value=Release(tag_name='v9.0.0',assets=[])):
        with patch('qt_update.sys.frozen',True,create=True):
            update=UpdateDialog()
            update.show();QTest.qWait(300)
            update.grab().save(str(output/'update-ready.png'))
            resume=Event()
            def fixture_download(release,destination,progress,cancel):
                progress(45)
                resume.wait(2)
                progress(100)
                return Path(temp)/'fixture.exe'
            with patch('qt_update.download_release',side_effect=fixture_download):
                QTest.mouseClick(update.action,Qt.MouseButton.LeftButton)
                QTest.qWait(300)
                update.grab().save(str(output/'update-progress.png'))
                resume.set();QTest.qWait(200)
                update.grab().save(str(output/'update-complete.png'))
                update.reject()
    with patch('qt_update.check_release',side_effect=UpdateError('Network unavailable')):
        update=UpdateDialog();update.show();QTest.qWait(300)
        assert update.action.isEnabled()
        update.grab().save(str(output/'update-error.png'))
        update.reject()
    island.close()
backdrop.close()
print('PASS: 10 action steps, hover to card, API handoff, save success/failure, update empty state')

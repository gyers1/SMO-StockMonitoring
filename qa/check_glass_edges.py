import sys,json
from pathlib import Path
from concurrent.futures import Future
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qt_app import configure_fonts
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QPointF,Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QCursor
from qt_model import TickerModel
from qt_island import GlassIsland
app=QApplication([]);configure_fonts(app)
path=ROOT/'qa/glass-edge-state.json';path.write_text('{"groups":{"empty":[],"one":["005930.KS"]},"selected_group":"empty"}')
model=TickerModel(path)
old=Future();old.set_running_or_notify_cancel();model._pending=old;model._pending_query='삼'
model.set_query('삼');before=list(model.results);old.set_result([]);model._poll();assert model.results==before
window=GlassIsland(model);window.show();area=app.primaryScreen().availableGeometry()
window.anchor=QPointF(area.right()-55,area.top()+100)
window.transition('orb');window.suppressed=True
failures=[]
def begin():
 window.suppressed=False
 QCursor.setPos((window.anchor+QPointF(18,18)).toPoint())
 QTimer.singleShot(1200,click)
def click():
 try:
  assert window.mode=='ribbon' and not window.pinned
  QTest.mouseClick(window,Qt.MouseButton.LeftButton,pos=window.mapFromGlobal((window.anchor+QPointF(18,18)).toPoint()))
  assert window.mode=='ribbon' and window.pinned
  assert window.stock_text(0)[0]=='관심 종목을 추가하세요'
  model.set_group('one');assert len(window.symbols)==1
  assert window.stock_text(99)[0]=='삼성전자'
  print('RIGHT-EDGE pin + empty/single group + stale search PASS')
 except BaseException as e:
  failures.append(str(e));print('FAIL',e)
 window.close()
QTimer.singleShot(1000,begin);QTimer.singleShot(6000,window.close);app.exec()
if failures:raise SystemExit(1)

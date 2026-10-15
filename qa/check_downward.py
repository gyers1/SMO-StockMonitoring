import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from qt_model import TickerModel
from qt_island import GlassIsland
app=QApplication([])
with tempfile.TemporaryDirectory() as temporary:
    model=TickerModel(Path(temporary)/'state.json')
    area=app.primaryScreen().availableGeometry()
    model.x=area.center().x()-18
    model.y=area.center().y()+40
    island=GlassIsland(model)
    island.show()
    ribbon=island.destination('ribbon')
    panel=island.destination('dashboard')
    try:
        assert panel.top()==ribbon.top(), 'Opening dashboard moves the reading position upwards'
        assert panel.bottom()<=area.bottom()-10
        island.open_dashboard('quotes')
        QTest.qWait(1100)
        assert island.dashboard.rect().contains(island.dashboard.status.geometry())
        island.grab().save(str(Path(__file__).parent/'revision/downward-center.png'))
        island.back_to_ribbon();QTest.qWait(1000)
        assert abs(island.values[1]-ribbon.top())<.1
        island.anchor=QPointF(model.x,area.bottom()-45)
        island.open_dashboard('quotes');QTest.qWait(1100)
        assert island.destination('dashboard').bottom()<=area.bottom()-10
        assert island.dashboard.rect().contains(island.dashboard.status.geometry())
        island.grab().save(str(Path(__file__).parent/'revision/downward-edge.png'))
    finally: island.close()
print('PASS: downward expansion, stable return, footer visible at lower edge')

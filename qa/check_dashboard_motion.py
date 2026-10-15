import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from qt_model import TickerModel
from qt_island import GlassIsland
app=QApplication([])
with tempfile.TemporaryDirectory() as temporary:
    model=TickerModel(Path(temporary)/'state.json')
    island=GlassIsland(model)
    island.show()
    island.transition('ribbon',True)
    QTest.qWait(1000)
    island.open_dashboard('quotes')
    QTest.qWait(150)
    try:
        assert island.dashboard.isVisible(), 'Blank panel: dashboard is hidden during expansion'
        assert island.fade.opacity() > .25, 'Search content still invisible'
        island.grab().save(str(Path(__file__).parent/'revision/dashboard-mid.png'))
        QTest.qWait(1000)
        assert not island.morphing
        assert island.dashboard.entry.isVisible()
        island.grab().save(str(Path(__file__).parent/'revision/dashboard-settled.png'))
    finally:
        island.close()
print('PASS: search content visible during expansion and after settlement')

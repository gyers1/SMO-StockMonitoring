from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from qt_startup import StartupSplash


def test_entrance_stays_vertical_at_saved_icon_position():
    app = QApplication.instance() or QApplication([])
    destination = QPointF(430, 330)
    splash = StartupSplash(destination)
    splash.timer.stop()
    splash.reduced = False
    expected = destination + QPointF(18, 18) - QPointF(splash.pos())
    positions = [splash.pose(step / 100)[0] for step in range(101)]
    assert all(abs(point.x() - expected.x()) < .001 for point in positions)
    assert positions[-1] == expected
    assert min(point.y() for point in positions) < expected.y() - 80
    splash.close()

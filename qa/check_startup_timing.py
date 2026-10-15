import json
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from qt_startup import StartupSplash
app=QApplication([])
center=app.primaryScreen().availableGeometry().center()
splash=StartupSplash(QPointF(center))
samples=[]
splash.timer.timeout.connect(lambda:samples.append(time.perf_counter()))
splash.finished.connect(app.quit)
splash.show()
app.exec()
intervals=[(b-a)*1000 for a,b in zip(samples,samples[1:])]
result={'frame_callbacks':len(samples),'median_interval_ms':round(statistics.median(intervals),2),'p95_interval_ms':round(sorted(intervals)[int(len(intervals)*.95)],2),'screen_refresh_hz':app.primaryScreen().refreshRate(),'note':'Qt callback cadence, not compositor FPS'}
Path(__file__).with_name('revision').joinpath('timing.json').write_text(json.dumps(result),encoding='utf-8')
print(json.dumps(result))

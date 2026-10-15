"""A forced exit during first guide must not cause another automatic guide."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from native_windows import find_window,exit_from_menu
root=Path(__file__).resolve().parents[1]
exe=root/'dist/SMO/SMO.exe'
with tempfile.TemporaryDirectory(prefix='SMO-guide-once-') as temp:
    env=dict(os.environ,LOCALAPPDATA=temp,PYTHONPATH='',PYTHONHOME='')
    first=subprocess.Popen([str(exe)],cwd=temp,env=env)
    try:
        for _ in range(150):
            if find_window(first.pid,'SMO 사용 안내'):break
            assert first.poll() is None
            time.sleep(.1)
        else:raise AssertionError('Guide missing on first launch')
        assert 'shown=true' in (Path(temp)/'SMO/guide.ini').read_text(encoding='utf-8').lower()
    finally:
        first.terminate();first.wait(timeout=15)
    second=subprocess.Popen([str(exe),'--guide'],cwd=temp,env=env)
    try:
        for _ in range(150):
            window=find_window(second.pid,'SMO · Stock Monitor')
            if window:break
            assert second.poll() is None
            time.sleep(.1)
        time.sleep(2)
        assert not find_window(second.pid,'SMO 사용 안내'),'Guide repeated after interrupted first launch'
        exit_from_menu(window)
        assert second.wait(timeout=25)==0
    finally:
        if second.poll() is None:second.terminate();second.wait(timeout=15)
print('PASS: interrupted first guide does not repeat, including legacy --guide argument')

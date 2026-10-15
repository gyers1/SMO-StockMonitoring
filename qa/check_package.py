"""Run the frozen build from an unrelated directory with isolated user data."""
from __future__ import annotations
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from ctypes import wintypes
from native_windows import find_window, exit_from_menu
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

root = Path(__file__).resolve().parents[1]
exe = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'dist/SMO/SMO.exe'
app = QApplication([])
backdrop = QWidget(None, Qt.WindowType.WindowStaysOnTopHint)
backdrop.setStyleSheet("background:#303541;")
backdrop.showMaximized()
app.processEvents()
user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
with tempfile.TemporaryDirectory(prefix='SMO-package-') as temporary:
    env = dict(os.environ, LOCALAPPDATA=temporary, PYTHONPATH='', PYTHONHOME='')
    proc = subprocess.Popen([str(exe)], cwd=temporary, env=env)
    handle = None
    try:
        for _ in range(200):
            handle = find_window(proc.pid, 'SMO · Stock Monitor')
            if handle:
                owner = wintypes.DWORD()
                user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
                if owner.value == proc.pid:
                    break
            assert proc.poll() is None, 'Packaged application exited before creating a window'
            time.sleep(.1)
        assert handle, 'No SMO window'
        time.sleep(1)
        coach = find_window(proc.pid, 'SMO 사용 안내')
        assert coach, 'First-run guide did not open'
        user32.PostMessageW(coach, 0x10, 0, 0)
        time.sleep(1)
        assert (Path(temporary) / 'SMO/guide.ini').is_file()
        assert proc.poll() is None, 'Closing guide unexpectedly ended application'
        duplicate = subprocess.run([str(exe)], cwd=temporary, env=env, timeout=15)
        assert duplicate.returncode == 0
        time.sleep(.5)
        screen = app.primaryScreen()
        assert screen is not None
        bounds = wintypes.RECT()
        user32.GetWindowRect(handle, ctypes.byref(bounds))
        assert screen.grabWindow(0, bounds.left, bounds.top, bounds.right-bounds.left, bounds.bottom-bounds.top).save(str(root / 'qa/package-orb.png'))
        user32.SetCursorPos(5, 5)
        time.sleep(.6)
        user32.GetWindowRect(handle, ctypes.byref(bounds))
        cursor_set = user32.SetCursorPos((bounds.left + bounds.right)//2, (bounds.top + bounds.bottom)//2)
        for _ in range(50):
            time.sleep(.1)
            user32.GetWindowRect(handle, ctypes.byref(bounds))
            if bounds.right - bounds.left > 400:
                break
        cursor = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(cursor))
        assert bounds.right - bounds.left > 400, f'Hover did not expand ribbon: window={(bounds.left,bounds.top,bounds.right,bounds.bottom)}, cursor={(cursor.x,cursor.y)}, set_cursor_ok={cursor_set}'
        assert screen.grabWindow(0, bounds.left, bounds.top, bounds.right-bounds.left, bounds.bottom-bounds.top).save(str(root / 'qa/package-ribbon.png'))
        for _ in range(100):
            time.sleep(.1)
            user32.GetWindowRect(handle, ctypes.byref(bounds))
            if bounds.right - bounds.left == 480:
                break
        assert bounds.right - bounds.left == 480, 'Ribbon animation did not settle'
        ribbon_top = bounds.top
        x, y = bounds.right - bounds.left - 89, 31
        user32.PostMessageW(handle, 0x201, 1, (y << 16) | x)
        user32.PostMessageW(handle, 0x202, 0, (y << 16) | x)
        for _ in range(50):
            time.sleep(.1)
            user32.GetWindowRect(handle, ctypes.byref(bounds))
            if bounds.bottom - bounds.top > 300:
                break
        for _ in range(100):
            time.sleep(.1)
            user32.GetWindowRect(handle, ctypes.byref(bounds))
            if bounds.right - bounds.left == 480:
                break
        assert bounds.bottom - bounds.top > 300, 'Frozen search page did not open'
        assert abs(bounds.top - ribbon_top) <= 2, f'Frozen top changed: {ribbon_top} -> {bounds.top}'
        assert screen.grabWindow(0, bounds.left, bounds.top, bounds.right-bounds.left, bounds.bottom-bounds.top).save(str(root / 'qa/package-dashboard.png'))
        user32.PostMessageW(handle, 0x10, 0, 0)
        time.sleep(.4)
        assert proc.poll() is None, 'Closing floating window must keep tray process alive'
        assert not user32.IsWindowVisible(handle)
        subprocess.run([str(exe)], cwd=temporary, env=env, check=True, timeout=15)
        time.sleep(.8)
        assert user32.IsWindowVisible(handle), 'Relaunch did not restore hidden app'
        exit_from_menu(handle)
        assert proc.wait(timeout=25) == 0
        state = Path(temporary) / 'SMO/ticker_state.json'
        assert state.is_file()
        payload = json.loads(state.read_text(encoding='utf-8'))
        assert 'groups' in payload
        restarted = subprocess.Popen([str(exe)], cwd=temporary, env=env)
        try:
            reopened = None
            for _ in range(100):
                reopened = find_window(restarted.pid, 'SMO · Stock Monitor')
                if reopened:
                    break
                assert restarted.poll() is None
                time.sleep(.1)
            time.sleep(.5)
            assert restarted.poll() is None
            assert not find_window(restarted.pid, 'SMO 사용 안내'), 'Guide repeated after completion'
            reopened = find_window(restarted.pid, 'SMO · Stock Monitor')
            assert reopened
            exit_from_menu(reopened)
            assert restarted.wait(timeout=25) == 0
        finally:
            if restarted.poll() is None:
                restarted.terminate()
                restarted.wait(timeout=10)

        result = {'guide_not_repeated':True, 'first_run_guide':True, 'standalone_start':True, 'native_window':True, 'duplicate_rejected':True,
                  'downward_dashboard':True, 'user_data_saved':True, 'clean_exit':True, 'close_to_tray':True, 'relaunch_restores':True, 'executable':str(exe)}
        (root / 'qa/package-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)

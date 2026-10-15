"""Launch the actual frozen app through an isolated Windows Shell Link."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pefile
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication

from native_windows import exit_from_menu, find_window, installed_window, user32

root = Path(__file__).resolve().parents[1]
exe = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'dist/SMO/SMO.exe'
app = QApplication([])
assert not QIcon(str(root / 'assets/smo.ico')).isNull()
with pefile.PE(str(exe)) as pe:
    resources = {item.id: item.directory.entries for item in pe.DIRECTORY_ENTRY_RESOURCE.entries}
    assert len(resources[3]) == 7, 'Executable must embed seven native SMO icon sizes'
    assert resources[14], 'Executable has no icon group'

with tempfile.TemporaryDirectory(prefix='SMO-shortcut-') as temporary:
    link = Path(temporary) / 'SMO.lnk'
    def literal(value: Path) -> str:
        return "'" + str(value).replace("'", "''") + "'"
    script = f'''$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut({literal(link)})
$link.TargetPath={literal(exe)}
$link.WorkingDirectory={literal(exe.parent)}
$link.IconLocation={literal(exe)}+',0'
$link.Save()
'''
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    subprocess.run(['powershell.exe', '-NoProfile', '-EncodedCommand', encoded], check=True, timeout=20)
    previous = os.environ.get('LOCALAPPDATA')
    os.environ['LOCALAPPDATA'] = temporary
    tested = None
    try:
        os.startfile(str(link))
        for _ in range(150):
            tested = installed_window(str(exe))
            if tested:
                break
            time.sleep(.1)
        assert tested, 'Shortcut did not create the actual SMO window'
        pid, handle = tested
        time.sleep(2)
        coach = find_window(pid, 'SMO 사용 안내')
        if coach:
            user32.PostMessageW(coach, 0x10, 0, 0)
            time.sleep(.5)
        user32.PostMessageW(handle, 0x10, 0, 0)
        time.sleep(.5)
        assert not user32.IsWindowVisible(handle)
        os.startfile(str(link))
        for _ in range(60):
            if user32.IsWindowVisible(handle):
                break
            time.sleep(.1)
        assert user32.IsWindowVisible(handle), 'Second shortcut launch did not recover hidden SMO'
        time.sleep(.5)
        bounds = wintypes.RECT()
        user32.GetWindowRect(handle, ctypes.byref(bounds))
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        assert screen is not None
        center = screen.availableGeometry().center()
        assert abs((bounds.left + bounds.right) / 2 - center.x()) < 15
        assert abs((bounds.top + bounds.bottom) / 2 - center.y()) < 15
        screen.grabWindow(handle).save(str(root / 'qa/shortcut-restored.png'))
    finally:
        if previous is None:
            del os.environ['LOCALAPPDATA']
        else:
            os.environ['LOCALAPPDATA'] = previous
        if tested:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            process = kernel.OpenProcess(0x100000, False, tested[0])
            assert process, 'Shortcut-launched process disappeared before Exit test'
            try:
                exit_from_menu(tested[1])
                assert kernel.WaitForSingleObject(process, 30000) == 0, 'Shortcut-launched SMO did not exit'
            finally:
                kernel.CloseHandle(process)
result = {'shortcut_launch': True, 'relaunch_center_restore': True, 'embedded_icon_sizes': 7}
(root / 'qa/shortcut-result.json').write_text(json.dumps(result), encoding='utf-8')
print(json.dumps(result))

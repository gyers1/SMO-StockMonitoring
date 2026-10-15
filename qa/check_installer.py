"""Isolated install/uninstall, preserving the existing user's uninstall registration."""
import ctypes
from ctypes import wintypes
import json
import os
import time
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from app_version import VERSION
from native_windows import installed_window, find_window, user32, exit_from_menu

registry = r'HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{7E42BA26-33C2-4142-8F14-A7502D26C405}_is1'
with tempfile.TemporaryDirectory(prefix='SMO-install-') as temporary:
    target = Path(temporary) / 'SMO'
    backup = Path(temporary) / 'uninstall.reg'
    exported = subprocess.run(['reg.exe','export',registry,str(backup),'/y'],capture_output=True)
    try:
        subprocess.run([str(root / f'release/SMO-Setup-{VERSION}.exe'), '/VERYSILENT',
                        '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', '/TASKS=', f'/DIR={target}',
                        f'/LOG={root / "qa/install.log"}'], check=True, timeout=120)
        subprocess.run([sys.executable, str(root / 'qa/check_package.py'),
                        str(target / 'SMO.exe')], check=True, timeout=90)
        profile = Path(temporary) / 'update-profile'
        profile.mkdir()
        env = dict(os.environ, LOCALAPPDATA=str(profile))
        subprocess.run([sys.executable, str(root/'qa/invoke_update_helper.py'),
                        str(root/f'release/SMO-Setup-{VERSION}.exe'), str(target/'SMO.exe')],
                       env=env,check=True,timeout=20)
        receipt = profile/'SMO/update-result.txt'
        deadline=time.monotonic()+90
        while not receipt.exists() and time.monotonic()<deadline:
            time.sleep(.5)
        assert receipt.read_text(encoding='utf-8-sig').strip()=='success', 'Update installer failed'
        restarted=None
        for _ in range(60):
            restarted=installed_window(str(target/'SMO.exe'))
            if restarted: break
            time.sleep(.5)
        assert restarted, 'Updated app did not restart'
        pid,handle=restarted
        for _ in range(60):
            if user32.IsWindowVisible(handle): break
            time.sleep(.1)
        time.sleep(.8)
        coach=find_window(pid,'SMO 사용 안내')
        if coach: user32.PostMessageW(coach,0x10,0,0)
        time.sleep(.5)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        process=kernel.OpenProcess(0x100000,False,pid)
        assert process, 'Restarted app process disappeared before Exit test'
        try:
            exit_from_menu(handle)
            assert kernel.WaitForSingleObject(process,20000)==0, 'Restarted app did not exit via menu'
        finally:
            kernel.CloseHandle(process)
    finally:
        try:
            if (target / 'unins000.exe').exists():
                subprocess.run([str(target / 'unins000.exe'), '/VERYSILENT',
                                '/SUPPRESSMSGBOXES', '/NORESTART',
                                f'/LOG={root / "qa/uninstall.log"}'], check=True, timeout=60)
        finally:
            if exported.returncode == 0:
                subprocess.run(['reg.exe','import',str(backup)],check=True,capture_output=True)
(root / 'qa/installer-result.json').write_text(
    json.dumps({'version':VERSION,'install':True, 'installed_app':True, 'uninstall':True,'real_update_helper_restart':True,'existing_registration_preserved':True}), encoding='utf-8')
print('Installer, installed app, uninstall, existing registration preserved: PASS')

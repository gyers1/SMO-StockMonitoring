from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import sys

from app_paths import DATA_DIR
from update_service import UpdateError


def install_and_restart(installer: Path) -> None:
    if not getattr(sys, 'frozen', False):
        raise UpdateError('개발 실행에서는 설치하지 않습니다. 배포판에서 업데이트할 수 있어요.')
    executable = Path(sys.executable).resolve()
    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"
    target = literal(str(executable.parent))
    setup = literal(str(installer.resolve()))
    app = literal(str(executable))
    receipt = literal(str(DATA_DIR / 'update-result.txt'))
    script = f'''
$ErrorActionPreference = 'Stop'
Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue
try {{
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS', ('/DIR="' + {target} + '"'))
    $process = Start-Process -FilePath {setup} -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {{ throw 'Installer failed' }}
    Set-Content -LiteralPath {receipt} -Value 'success' -Encoding UTF8
}} catch {{
    Set-Content -LiteralPath {receipt} -Value 'failed' -Encoding UTF8
}} finally {{
    Start-Process -FilePath {app}
}}
'''
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
                     creationflags=subprocess.CREATE_NO_WINDOW,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

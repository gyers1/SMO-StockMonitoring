"""Keep crash locations without recording exception messages or local variables."""
from __future__ import annotations

import faulthandler
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import TextIO


def install_diagnostics(directory: Path) -> TextIO | None:
    path = directory / 'runtime.log'
    try:
        if path.exists() and path.stat().st_size > 256_000:
            path.replace(directory / 'runtime.previous.log')
        stream = path.open('a', encoding='utf-8')
    except OSError:
        return None
    faulthandler.enable(stream)

    def record(kind: type[BaseException], value: BaseException, trace: TracebackType | None) -> None:
        stream.write(f'\n{datetime.now(timezone.utc).isoformat()} {kind.__name__}\n')
        for frame in traceback.extract_tb(trace):
            stream.write(f'  {Path(frame.filename).name}:{frame.lineno} {frame.name}\n')
        stream.flush()

    sys.excepthook = record
    return stream

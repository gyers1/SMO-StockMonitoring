from pathlib import Path
import os
from typing import Final

DATA_DIR: Final = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SMO'
DATA_DIR.mkdir(parents=True, exist_ok=True)

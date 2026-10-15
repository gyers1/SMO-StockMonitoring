import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from update_install import install_and_restart
installer=Path(sys.argv[1]).resolve()
sys.executable=str(Path(sys.argv[2]).resolve())
sys.frozen=True
install_and_restart(installer)

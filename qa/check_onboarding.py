from pathlib import Path
import runpy

# The action-driven guide supersedes the former Next-button walkthrough.
runpy.run_path(str(Path(__file__).with_name("check_revision.py")), run_name="__main__")

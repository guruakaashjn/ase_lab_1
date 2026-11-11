"""Creates a fresh copy of tinyledger in task4_tools/workspace/ and makes it a git repository.

Run this before every agent run:
    uv run python task4_tools/reset_workspace.py

After the run, create the diff with:
    git -C task4_tools/workspace diff > task4_tools/final.diff
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "tinyledger"
WORKSPACE = HERE / "workspace"


def _force_remove(path: Path) -> None:
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                os.chmod(Path(root) / name, stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(path)


def main() -> None:
    if WORKSPACE.exists():
        _force_remove(WORKSPACE)
    shutil.copytree(SOURCE, WORKSPACE, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    git = ["git", "-C", str(WORKSPACE), "-c", "user.name=lab", "-c", "user.email=lab@example.org"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "initial state"], check=True)
    print(f"Fresh workspace ready: {WORKSPACE}")


if __name__ == "__main__":
    main()

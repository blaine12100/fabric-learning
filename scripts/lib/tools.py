"""Python CLI tools the plugin installs for itself (e.g. yt-dlp), in one private virtual environment
under the cache directory, so nothing is installed system-wide."""
import shutil
import subprocess
import sys
import venv
from pathlib import Path

from .config import cache_root
from .errors import CommandError

WINDOWS = sys.platform == "win32"
EXE = ".exe" if WINDOWS else ""


def env_dir() -> Path:
    return cache_root() / "venv"


def _bin(name: str) -> Path:
    return env_dir() / ("Scripts" if WINDOWS else "bin") / f"{name}{EXE}"


def install(package: str, command: str = None) -> str:
    """Create the private venv if needed and pip install/upgrade package. Returns the command's path."""
    print(f"Installing {package} into {env_dir()} (first use only)…", file=sys.stderr)
    venv.EnvBuilder(with_pip=True, clear=False).create(env_dir())
    r = subprocess.run([str(_bin("python")), "-m", "pip", "install", "-q", "-U", package], capture_output=True, text=True)
    if r.returncode != 0:
        raise CommandError(f"could not install {package}: {r.stderr.strip()[-400:]}")
    return str(_bin(command or package))


def ensure(package: str, command: str = None) -> str:
    """Path to command: the private copy, else one on PATH, else install it."""
    exe = _bin(command or package)
    if exe.exists():
        return str(exe)
    return shutil.which(command or package) or install(package, command)

"""Python CLI tools the plugin installs for itself (e.g. yt-dlp), in one private virtual environment
under the cache directory, so nothing is installed system-wide."""
import shutil
import subprocess
import sys
import venv
from pathlib import Path

try:
    import fcntl  # POSIX only; on Windows concurrent first-use installs aren't serialised
except ImportError:
    fcntl = None

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
    env_dir().parent.mkdir(parents=True, exist_ok=True)
    # one installer at a time: gather.py can start two youtube steps on first use
    with open(cache_root() / "venv.lock", "a") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        exe = _bin(command or package)
        if exe.exists():  # another process finished the install while we waited
            return str(exe)
        print(f"Installing {package} into {env_dir()} (first use only)…", file=sys.stderr)
        try:
            venv.EnvBuilder(with_pip=True, clear=False).create(env_dir())
            r = subprocess.run([str(_bin("python")), "-m", "pip", "install", "-q", "-U", package],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        except (OSError, subprocess.CalledProcessError) as e:  # e.g. Debian/Ubuntu without python3-venv
            raise CommandError(f"could not create a virtual environment for {package}: {e}")
        if r.returncode != 0:
            raise CommandError(f"could not install {package}: {r.stderr.strip()[-400:]}")
        return str(exe)


def ensure(package: str, command: str = None) -> str:
    """Path to command: the private copy, else one on PATH, else install it."""
    exe = _bin(command or package)
    if exe.exists():
        return str(exe)
    return shutil.which(command or package) or install(package, command)

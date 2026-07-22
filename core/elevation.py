"""
Administrator-privilege self-elevation.

Why this is necessary
----------------------
Windows enforces UIPI (User Interface Privilege Isolation): a process
running at a lower integrity/privilege level is blocked by the OS from
sending synthetic input to a window owned by a HIGHER-privilege process
— regardless of how that input is generated (this applies even to raw
`SendInput` hardware-level events). If KeyMagic runs as a normal
user but the foreground app is "Run as administrator" (a common state for
IDEs, admin consoles, some installers), every hotkey would silently fail
against that window.

Running KeyMagic itself elevated puts it at the same or higher
integrity level as anything else on the desktop, so its simulated
Ctrl+C/Ctrl+V/Shift+Home always reach the foreground window.
"""

from __future__ import annotations

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """Return True if the current process already holds administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        logger.exception("Could not determine current elevation state.")
        return False


def relaunch_elevated() -> None:
    """
    Re-launch this same script/executable with a UAC elevation prompt, then
    exit the current (non-elevated) process. Only relevant when running as
    a plain `python main.py` — a PyInstaller build should instead embed an
    application manifest (`pyinstaller --uac-admin ...`) so Windows prompts
    for elevation automatically at launch with no relaunch step needed.
    """
    params = " ".join(f'"{arg}"' for arg in sys.argv)
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    # ShellExecuteW returns a value > 32 on success.
    if int(result) <= 32:
        logger.error("User declined the UAC elevation prompt (or it failed); exiting.")
    sys.exit(0)


def ensure_admin() -> None:
    """Elevate-and-restart if not already running with administrator privileges."""
    if not is_admin():
        logger.info("Not running elevated — requesting UAC elevation and restarting.")
        relaunch_elevated()

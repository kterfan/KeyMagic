"""
"Start with Windows" support.

Implemented with the per-user Run key
(HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run) rather than a
scheduled task or the Startup folder:

  * HKCU needs no administrator rights to write, so toggling it from the
    tray works even though the app itself normally runs elevated.
  * It is per-user, so installing for one account does not silently add
    a startup entry for everyone on the machine.
  * Windows' own Settings > Startup Apps lists and can disable it, which
    users expect to work.

Frozen (PyInstaller) and source runs need different command lines, so the
command is derived from `sys.frozen` rather than assumed.
"""

from __future__ import annotations

import logging
import os
import sys
import winreg

from .config import UI

logger = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command() -> str:
    """The exact command Windows should run at logon, correctly quoted."""
    if getattr(sys, "frozen", False):
        # Installed build: the executable launches itself.
        return f'"{sys.executable}"'
    # Running from source: invoke the interpreter against main.py.
    main_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return f'"{sys.executable}" "{main_script}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, UI.APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        logger.exception("Could not read the autostart registry value.")
        return False


def enable() -> bool:
    """Register the app to launch at logon. Returns True on success."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, UI.APP_NAME, 0, winreg.REG_SZ, _launch_command())
        logger.info("Autostart enabled.")
        return True
    except OSError:
        logger.exception("Could not enable autostart.")
        return False


def disable() -> bool:
    """Remove the logon entry. Succeeds silently if it was not present."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, UI.APP_NAME)
        logger.info("Autostart disabled.")
        return True
    except FileNotFoundError:
        return True  # already absent — the desired end state
    except OSError:
        logger.exception("Could not disable autostart.")
        return False


def apply(enabled: bool) -> bool:
    """Make the registry match `enabled`."""
    return enable() if enabled else disable()

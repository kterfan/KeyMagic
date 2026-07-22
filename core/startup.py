"""
"Start with Windows" support.

Why a scheduled task and not the Run key
-----------------------------------------
The obvious approach is HKCU\\...\\CurrentVersion\\Run, and that is what this
module used originally. It does not work for KeyMagic: the executable ships a
`requireAdministrator` manifest (it has to, or Windows UIPI blocks it from
sending input to elevated windows), and **Windows silently skips Run-key
entries that would need an elevation prompt at logon**. No error, no prompt,
no app — the feature looked implemented and did nothing.

A Task Scheduler entry with RunLevel=HIGHEST is the supported way to start an
elevated program at logon: the task carries the elevation, so no UAC prompt
appears and the app actually launches.

The task is created with `schtasks.exe` rather than the COM API because it
avoids a pywin32 dependency for something this small, and the command line is
easy to audit. Creating a HIGHEST-run-level task needs administrator rights,
which the app already has.

Legacy Run-key entries from earlier versions are removed on every apply, so
upgrading users don't keep a dead registry value around.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import winreg

from .config import UI

logger = logging.getLogger(__name__)

_TASK_NAME = UI.APP_NAME
_LEGACY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Keeps schtasks from flashing a console window on a windowed build.
_NO_WINDOW = 0x08000000


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        creationflags=_NO_WINDOW,
        check=False,
    )


def _target_command() -> str:
    """The command the task should launch, correctly quoted."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return f'"{sys.executable}" "{main_script}"'


def _remove_legacy_run_entry() -> None:
    """Drop the old Run-key value left behind by pre-task versions."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _LEGACY_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, UI.APP_NAME)
        logger.info("Removed legacy Run-key autostart entry.")
    except FileNotFoundError:
        pass  # nothing to clean up
    except OSError:
        logger.exception("Could not remove the legacy Run-key entry.")


def is_enabled() -> bool:
    """True if the logon task exists."""
    result = _run(["schtasks", "/Query", "/TN", _TASK_NAME])
    return result.returncode == 0


def enable() -> bool:
    """Create (or replace) the at-logon task. Returns True on success."""
    result = _run([
        "schtasks", "/Create",
        "/TN", _TASK_NAME,
        "/TR", _target_command(),
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",   # carries the elevation, so no logon UAC prompt
        "/F",               # replace an existing task instead of failing
    ])
    if result.returncode == 0:
        logger.info("Autostart enabled (scheduled task, highest privileges).")
        _remove_legacy_run_entry()
        return True

    logger.error("Could not create the autostart task: %s", (result.stderr or result.stdout).strip())
    return False


def disable() -> bool:
    """Delete the logon task. Succeeds if it was already absent."""
    result = _run(["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"])
    _remove_legacy_run_entry()

    if result.returncode == 0:
        logger.info("Autostart disabled.")
        return True
    if not is_enabled():
        return True  # already gone — the desired end state

    logger.error("Could not delete the autostart task: %s", (result.stderr or result.stdout).strip())
    return False


def apply(enabled: bool) -> bool:
    """Make the system match `enabled`."""
    return enable() if enabled else disable()

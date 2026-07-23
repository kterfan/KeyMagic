"""
Single-instance guard.

Why this exists
----------------
KeyMagic claims F10 / Ctrl+G / Ctrl+T through `RegisterHotKey`, which is
*exclusive* — only one process can own a given combination. A second
instance therefore starts, silently fails to register any hotkey, and now
sits in the tray doing nothing while its hotkeys appear dead. That is easy
to hit in normal use: the logon scheduled task launches the app, then the
user clicks the Start-menu shortcut, and suddenly there are two tray icons
and one of them is inert.

This guard turns a second launch into a hand-off. The first instance owns a
hidden top-level window with a known class name; a second launch finds that
window, tells it to open the control panel (the natural "it's already
running, here it is" response), and exits without registering anything.

Design choices
--------------
* A **named mutex** is the instance token — the canonical Win32 way to ask
  "am I already running for this user". A ``Local\\`` prefix scopes it to
  the session, i.e. one instance per logged-in user.
* Signalling goes through a **hidden ordinary window found by class name**,
  not a broadcast. `PostMessage(HWND_BROADCAST, ...)` does not reach a
  thread message queue, and a message-only (HWND_MESSAGE) window is
  explicitly excluded from broadcasts — so a real, findable window is the
  dependable channel. The message id comes from `RegisterWindowMessage`,
  which returns the same value in both processes for the same string.
* The window runs on its own daemon thread with its own message loop, so it
  is independent of the hotkey listener and the Tk flyout.

The mutex handle and the window are held for the process lifetime and
released by the OS on exit, so a crash cannot leave a stale lock behind.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable, Optional

from .config import UI

logger = logging.getLogger(__name__)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

_MUTEX_NAME = f"Local\\{UI.APP_NAME}_SingleInstance"
_WINDOW_CLASS = f"{UI.APP_NAME}_IPC_Window"
_SHOW_PANEL_MESSAGE = f"{UI.APP_NAME}_ShowPanel"

ERROR_ALREADY_EXISTS = 183

# LRESULT/handles are pointer-sized; wintypes doesn't define LRESULT, so use
# LPARAM (also pointer-sized) for it. Declaring argtypes/restypes explicitly
# matters here: without them ctypes assumes 32-bit ints for return values and
# handle arguments, which overflows on 64-bit Windows (CreateWindowExW's
# HINSTANCE argument raised "int too long to convert").
LRESULT = wintypes.LPARAM

# WNDPROC signature: LRESULT (*)(HWND, UINT, WPARAM, LPARAM)
_WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]

user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.PostMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]


class _WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


_mutex_handle = None  # module-level: lives as long as the process
_message_id: Optional[int] = None


def _show_panel_message_id() -> int:
    global _message_id
    if _message_id is None:
        _message_id = user32.RegisterWindowMessageW(_SHOW_PANEL_MESSAGE)
    return _message_id


def acquire() -> bool:
    """
    Try to become the single instance.

    True  -> this process is the first (and now sole) instance.
    False -> another instance already holds the lock; the caller should
             `signal_existing_instance()` and exit.
    """
    global _mutex_handle
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    last_error = ctypes.get_last_error()

    if not _mutex_handle:
        # Fail open — the guard is a nicety, not worth blocking startup over.
        logger.warning("CreateMutex failed (%d); continuing without the single-instance guard.", last_error)
        return True

    if last_error == ERROR_ALREADY_EXISTS:
        logger.info("Another KeyMagic instance is already running.")
        return False

    return True


def signal_existing_instance() -> None:
    """Ask the running instance to surface its control panel, then return."""
    hwnd = user32.FindWindowW(_WINDOW_CLASS, None)
    if hwnd:
        user32.PostMessageW(hwnd, _show_panel_message_id(), 0, 0)
        logger.info("Signalled the existing instance to show its panel.")
    else:
        # The other instance holds the mutex but has no window yet (still
        # starting up). Nothing actionable; just don't start a second tray.
        logger.info("Existing instance found via mutex but its IPC window was not ready.")


def start_listener(on_show_panel: Callable[[], None]) -> None:
    """
    Create the hidden IPC window on a dedicated thread and run its message
    loop. `on_show_panel` is invoked whenever another launch asks this
    instance to open its panel.
    """
    ready = threading.Event()

    def _run() -> None:
        message_id = _show_panel_message_id()

        def _wndproc(hwnd, msg, wparam, lparam):
            if msg == message_id:
                try:
                    on_show_panel()
                except Exception:
                    logger.exception("Failed to show panel on IPC request.")
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        proc = _WNDPROC(_wndproc)

        wndclass = _WNDCLASS()
        wndclass.lpfnWndProc = proc
        wndclass.lpszClassName = _WINDOW_CLASS
        wndclass.hInstance = kernel32.GetModuleHandleW(None)

        atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            logger.warning("Could not register IPC window class (%d).", ctypes.get_last_error())
            ready.set()
            return

        hwnd = user32.CreateWindowExW(
            0, _WINDOW_CLASS, _WINDOW_CLASS, 0, 0, 0, 0, 0, None, None, wndclass.hInstance, None
        )
        # Keep a reference to the WNDPROC so it is not garbage-collected
        # while Windows still holds a pointer to it.
        _run.proc = proc  # type: ignore[attr-defined]
        ready.set()

        if not hwnd:
            logger.warning("Could not create IPC window (%d).", ctypes.get_last_error())
            return

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    threading.Thread(target=_run, daemon=True, name="SingleInstanceIPC").start()
    ready.wait(timeout=5.0)

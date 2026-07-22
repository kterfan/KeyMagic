"""
Global hotkey registration via the OS-native Win32 `RegisterHotKey` API.

Why not the `keyboard` library?
--------------------------------
`keyboard` implements global hotkeys with a low-level `WH_KEYBOARD_LL`
hook. To support `suppress=True` it must intercept and *buffer* every
press of a key that could begin a registered combination — including Ctrl,
because `ctrl+g` and `ctrl+t` are registered here. That buffering also
catches the synthetic Ctrl+C / Ctrl+V this app injects for itself, and
releases the pieces out of order: the target window then receives a bare
`c` instead of Ctrl+C, silently typing a stray character into the user's
document instead of copying. (Observed directly: typing `sghl` and hitting
F10 produced `سلامز` — that trailing `ز` is exactly `c` run through the
layout map.)

`RegisterHotKey` has none of that machinery. The OS itself claims the key
combination and delivers a `WM_HOTKEY` message to us; the foreground
application never sees the keystroke at all, and no hook sits in the path
of the input we inject. It also supports `MOD_NOREPEAT`, which makes
Windows ignore held-key auto-repeat at the source — so a single physical
press can only ever produce a single action, no debouncing needed.

The listener owns a dedicated thread because `RegisterHotKey` delivers
`WM_HOTKEY` to the thread that registered it, and that thread must run a
message loop — which cannot be the main thread here, since pystray's tray
icon already owns that.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable

user32 = ctypes.WinDLL("user32", use_last_error=True)

logger = logging.getLogger(__name__)

# Modifier flags for RegisterHotKey.
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


class HotkeyListener:
    """
    Registers OS-level global hotkeys and dispatches them to callbacks.

    Usage:
        listener = HotkeyListener()
        listener.register("f10", MOD_NOREPEAT, 0x79, my_callback)
        listener.start()
        ...
        listener.stop()
    """

    def __init__(self) -> None:
        self._registrations: list[tuple[str, int, int, Callable[[], None]]] = []
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()

    def register(self, label: str, modifiers: int, virtual_key: int, callback: Callable[[], None]) -> None:
        """
        Queue a hotkey for registration. Must be called before `start()`,
        because the actual RegisterHotKey call has to happen on the
        listener's own message-loop thread.
        """
        self._registrations.append((label, modifiers, virtual_key, callback))

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_message_loop, daemon=True, name="HotkeyListener")
        self._thread.start()
        self._ready.wait(timeout=5.0)

    def stop(self) -> None:
        if self._thread_id is not None:
            # Waking the loop with WM_QUIT lets it unregister cleanly on the
            # same thread that registered the hotkeys, as Windows requires.
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run_message_loop(self) -> None:
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        registered_ids: list[int] = []
        for index, (label, modifiers, virtual_key, callback) in enumerate(self._registrations, start=1):
            if user32.RegisterHotKey(None, index, modifiers | MOD_NOREPEAT, virtual_key):
                self._callbacks[index] = callback
                registered_ids.append(index)
                logger.info("Registered global hotkey '%s' (id=%d).", label, index)
            else:
                # Most common cause: another running application already
                # owns this exact combination system-wide.
                error = ctypes.get_last_error()
                logger.error("Failed to register hotkey '%s' (WinError %d) — is it already in use?", label, error)

        self._ready.set()

        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == WM_HOTKEY:
                    callback = self._callbacks.get(message.wParam)
                    if callback is not None:
                        callback()
        finally:
            for hotkey_id in registered_ids:
                user32.UnregisterHotKey(None, hotkey_id)
            logger.info("Hotkey listener stopped and all hotkeys unregistered.")

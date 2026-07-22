"""
Hardware-level keyboard input simulation via the raw Win32 `SendInput` API.

Why not just use `keyboard.send(...)`?
---------------------------------------
`keyboard.send()` is convenient, but it composes virtual-key codes without
always attaching a hardware scan code. Some applications — particularly
elevated/hardened ones, certain Electron/browser sandboxes, and strict
enterprise software — inspect the scan code (`wScan`) of incoming input
and silently discard synthetic key events that only carry a virtual-key
code with no matching scan code, treating them as suspicious/software-only
input.

This module builds `INPUT` structures by hand and always resolves a real
hardware scan code via `MapVirtualKeyW` before injecting through
`SendInput` with `KEYEVENTF_SCANCODE`. That is the same signal path a
physical keyboard driver produces, which is what makes it work uniformly
across Word, browsers, chat clients, IDEs, and terminals alike — not just
plain Win32 edit controls.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
MAPVK_VK_TO_VSC = 0

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_HOME = 0x24
VK_C = 0x43
VK_V = 0x56

# Home/End/arrows/Insert/Delete/PageUp/PageDown share a raw scan code with
# the numeric keypad; without KEYEVENTF_EXTENDEDKEY, Windows can resolve
# them as the keypad variant instead (behavior then depends on Num Lock
# state) rather than as navigation keys.
_EXTENDED_KEYS = {VK_HOME}

# Delay between individual key down/up events in a chord — long enough for
# the target application's message loop to register each state change,
# short enough to feel instantaneous to the user.
_KEY_STEP_DELAY_SECONDS = 0.015

ULONG_PTR = wintypes.WPARAM  # pointer-sized unsigned integer on both 32/64-bit


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    # SendInput validates that the INPUT struct we pass is exactly
    # sizeof(INPUT) as Windows defines it — which is sized by the LARGEST
    # union member (MOUSEINPUT, at 32 bytes on x64), not just the KEYBDINPUT
    # variant we actually use. Omitting the other two members here silently
    # shrinks our struct and makes SendInput reject every call with
    # ERROR_INVALID_PARAMETER (87).
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


def _send_key_event(virtual_key: int, key_up: bool) -> None:
    scan_code = user32.MapVirtualKeyW(virtual_key, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    if virtual_key in _EXTENDED_KEYS:
        flags |= KEYEVENTF_EXTENDEDKEY

    packet = _INPUT(
        type=INPUT_KEYBOARD,
        union=_INPUT_UNION(ki=_KEYBDINPUT(virtual_key, scan_code, flags, 0, 0)),
    )
    sent = user32.SendInput(1, ctypes.byref(packet), ctypes.sizeof(_INPUT))
    if sent != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def _send_chord(*virtual_keys: int) -> None:
    """Press every key down in order, then release in reverse order — a proper chord."""
    for vk in virtual_keys:
        _send_key_event(vk, key_up=False)
        time.sleep(_KEY_STEP_DELAY_SECONDS)
    for vk in reversed(virtual_keys):
        _send_key_event(vk, key_up=True)
        time.sleep(_KEY_STEP_DELAY_SECONDS)


def wait_for_modifiers_released(timeout: float = 1.0) -> None:
    """
    Block until the user physically lets go of Ctrl/Shift/Alt (or `timeout`
    elapses).

    A Ctrl-based hotkey fires the instant the final key goes down, while the
    user is still holding Ctrl. Injecting our own chord at that moment mixes
    real and synthetic modifier state — our trailing "Ctrl up" would tell
    Windows the key is released while the user still has it pressed, leaving
    the modifier stuck from the target app's point of view. Waiting for a
    clean slate first avoids the whole class of problem.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        held = any(
            user32.GetAsyncKeyState(vk) & 0x8000
            for vk in (VK_CONTROL, VK_SHIFT, VK_MENU)
        )
        if not held:
            return
        time.sleep(0.01)


def send_copy() -> None:
    """Hardware-level Ctrl+C."""
    _send_chord(VK_CONTROL, VK_C)


def send_paste() -> None:
    """Hardware-level Ctrl+V."""
    _send_chord(VK_CONTROL, VK_V)


def send_select_to_line_start() -> None:
    """Hardware-level Shift+Home — extends the selection back to the start of the current line."""
    _send_chord(VK_SHIFT, VK_HOME)

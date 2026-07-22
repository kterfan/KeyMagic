"""
Centralized, immutable configuration for the whole application.

Keeping every tunable constant in one place means the timing/retry behavior
of the clipboard engine (the most fragile part of this kind of tool) can be
tuned without hunting through business logic.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HotkeyBinding:
    """A single global hotkey, expressed the way RegisterHotKey wants it."""

    label: str          # human-readable, for logs and notifications
    modifiers: int      # bitwise OR of MOD_* flags (0 for none)
    virtual_key: int    # Win32 virtual-key code


# MOD_CONTROL, kept here to avoid importing the listener module into config.
_MOD_CONTROL = 0x0002


@dataclass(frozen=True)
class HotkeyConfig:
    LAYOUT_FIX: HotkeyBinding = HotkeyBinding("F10", 0, 0x79)
    SMART_SEARCH: HotkeyBinding = HotkeyBinding("Ctrl+G", _MOD_CONTROL, 0x47)
    QUICK_TRANSLATE: HotkeyBinding = HotkeyBinding("Ctrl+T", _MOD_CONTROL, 0x54)


@dataclass(frozen=True)
class ClipboardConfig:
    # How many times to retry a clipboard Open/Read/Write operation before
    # giving up. Windows clipboard is a single global resource — any other
    # process (including the one that owns the text we just copied) can be
    # holding it for a few milliseconds.
    MAX_RETRIES: int = 8
    RETRY_DELAY_SECONDS: float = 0.03

    # After sending Ctrl+C, how long we wait (in total) for the clipboard
    # sequence number to change before concluding "nothing was selected".
    COPY_TIMEOUT_SECONDS: float = 1.0
    COPY_POLL_INTERVAL_SECONDS: float = 0.02

    # Small settle delay before we send Ctrl+V, giving the foreground window
    # time to process the WM_CLIPBOARDUPDATE style notification.
    PRE_PASTE_DELAY_SECONDS: float = 0.05

    # Delay after Ctrl+V before we restore the user's original clipboard
    # content — must be long enough that the paste has actually completed.
    POST_PASTE_SETTLE_SECONDS: float = 0.15


@dataclass(frozen=True)
class UIConfig:
    APP_NAME: str = "KeyMagic"
    VERSION: str = "1.0.1"
    TOAST_DURATION: str = "short"  # win11toast: "short" or "long"
    LOG_FILENAME: str = "keymagic.log"


HOTKEYS = HotkeyConfig()
CLIPBOARD = ClipboardConfig()
UI = UIConfig()

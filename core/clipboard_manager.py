"""
Bulletproof clipboard manipulation.

Design rationale
-----------------
The naive approach to "copy selected text" is:
    1. send Ctrl+C
    2. sleep(0.1)
    3. read clipboard

This is a race condition by construction: the sleep duration is a guess,
and there is no guarantee the source application has finished writing to
the clipboard by the time you wake up.

Instead, this module uses the Windows clipboard *sequence number*
(`GetClipboardSequenceNumber`). Windows increments this counter every
single time the clipboard content changes, regardless of which process
changed it. By recording the sequence number immediately before sending
Ctrl+C and then polling until it changes (or a timeout elapses), we get a
deterministic, race-free signal that "yes, new data has landed" — with no
guessing about delays.

The clipboard is also a single shared OS resource: any process (Explorer,
antivirus clipboard scanners, the app you just copied from) can be holding
it open for a few milliseconds. All read/write operations are therefore
wrapped in a bounded retry loop with a short backoff, rather than crashing
on the first `pywintypes.error`.

Plain text only, always
------------------------
Rich editors (Microsoft Word, browser textareas, HTML-aware chat clients)
routinely place several clipboard formats at once — CF_UNICODETEXT,
CF_HTML, sometimes a bitmap rendering. This module only ever *reads*
CF_UNICODETEXT (ignoring any HTML/RTF/image payload sitting alongside it),
and `write_text()` calls `EmptyClipboard()` before setting exactly one
format, CF_UNICODETEXT. That combination guarantees the tool never carries
formatting, embedded styles, or images through a convert/paste cycle —
what goes back into the target application is always plain text, which is
what prevents paste corruption in strict editors like Word.

Finally, every action that touches the clipboard is expected to restore the
user's original clipboard content afterwards, so this tool never causes
"silent data loss" of whatever the user had copied before invoking it.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, TypeVar

import pywintypes
import win32clipboard
import win32con

from .config import CLIPBOARD

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class ClipboardError(Exception):
    """Raised when the clipboard cannot be accessed after all retries are exhausted."""


class ClipboardManager:
    """
    Thin, retry-hardened wrapper around the Win32 clipboard API.

    All public methods are safe to call repeatedly and never leave the
    clipboard open on exit (each Open is paired with a Close in a
    try/finally, even on failure).
    """

    def get_sequence_number(self) -> int:
        """Return the OS-wide clipboard sequence number (increments on every change)."""
        return win32clipboard.GetClipboardSequenceNumber()

    def _guarded(self, operation: Callable[[], _T], description: str) -> _T:
        """
        Run `operation` with the clipboard open, retrying on contention.

        Every public method here needs the identical open/retry/close
        dance, so it lives in exactly one place: the clipboard is always
        closed via try/finally even when the operation raises, and a
        transient `pywintypes.error` (another process holding the
        clipboard for a few ms) is retried rather than propagated.
        """
        last_error: Optional[Exception] = None
        for _ in range(CLIPBOARD.MAX_RETRIES):
            try:
                win32clipboard.OpenClipboard()
                try:
                    return operation()
                finally:
                    win32clipboard.CloseClipboard()
            except pywintypes.error as exc:
                last_error = exc
                time.sleep(CLIPBOARD.RETRY_DELAY_SECONDS)

        raise ClipboardError(
            f"Failed to {description} clipboard after {CLIPBOARD.MAX_RETRIES} retries: {last_error}"
        )

    def read_text(self) -> Optional[str]:
        """
        Return the current clipboard text, or None if the clipboard is
        empty or holds non-text data (e.g. an image or file list).

        Never raises for "no text available" — only raises ClipboardError
        if the clipboard itself could not be opened after all retries.
        """

        def _read() -> Optional[str]:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None

        return self._guarded(_read, "read")

    def write_text(self, text: str) -> None:
        """Set the clipboard to the given unicode text, with retry-on-contention."""

        def _write() -> None:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)

        self._guarded(_write, "write")

    def clear(self) -> None:
        """Empty the clipboard entirely (used when there was nothing to restore)."""
        self._guarded(win32clipboard.EmptyClipboard, "clear")

    def capture_selection_text(self, send_copy_fn, timeout: Optional[float] = None) -> Optional[str]:
        """
        Trigger a copy of the currently selected text (via `send_copy_fn`,
        typically a Ctrl+C simulator) and race-free wait for the clipboard
        to actually update, then return the resulting text.

        `timeout` overrides the default wait — useful for a quick "is
        anything even selected?" probe that shouldn't stall the user for a
        full second before falling back to another strategy.

        Returns None if no selection was copied within the timeout window,
        or if what landed on the clipboard is not plain text.
        """
        before_seq = self.get_sequence_number()

        send_copy_fn()

        deadline = time.monotonic() + (timeout if timeout is not None else CLIPBOARD.COPY_TIMEOUT_SECONDS)
        while time.monotonic() < deadline:
            if self.get_sequence_number() != before_seq:
                break
            time.sleep(CLIPBOARD.COPY_POLL_INTERVAL_SECONDS)
        else:
            logger.info("No clipboard change detected after copy — likely no active selection.")
            return None

        return self.read_text()

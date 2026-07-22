"""
Modern Windows toast notifications for visual feedback.

Wrapped in its own class so the rest of the app never has to know or care
which underlying library renders the toast, and so a failure to render a
toast (e.g. running under an unusual Windows build) never crashes an
action — user-facing feedback is a nice-to-have, not a correctness path.

Two independent suppression controls, because they are different
complaints: `muted` keeps the toast visible but silences the notification
*sound* (a "ding-dong" on every hotkey gets old fast), while
`show_toasts=False` hides the popup entirely.
"""

from __future__ import annotations

import logging
import threading

from .config import UI
from .i18n import Translator
from .settings import Settings

logger = logging.getLogger(__name__)

try:
    from win11toast import toast as _win11_toast
except ImportError:  # pragma: no cover - environment without the dependency
    _win11_toast = None
    logger.warning("win11toast is not installed; toast notifications are disabled.")

# WinRT audio payload that renders a toast with no sound at all.
_SILENT_AUDIO = {"silent": "true"}


class ToastNotifier:
    """Fire-and-forget Windows toasts honouring the user's sound/visibility prefs."""

    def __init__(self, settings: Settings, translator: Translator) -> None:
        self._settings = settings
        self._t = translator

    def _show(self, message: str) -> None:
        if not self._settings.show_toasts:
            return

        if _win11_toast is None:
            logger.info("Toast (unavailable): %s", message)
            return

        muted = self._settings.muted

        def _run() -> None:
            try:
                _win11_toast(
                    UI.APP_NAME,
                    message,
                    duration=UI.TOAST_DURATION,
                    app_id=UI.APP_NAME,
                    audio=_SILENT_AUDIO if muted else None,
                )
            except Exception:
                logger.exception("Failed to display toast notification.")

        # Toast rendering goes through COM/WinRT; do it off the hotkey
        # thread so a slow or misbehaving notification never delays the
        # next keystroke the user makes.
        threading.Thread(target=_run, daemon=True).start()

    def notify(self, key: str) -> None:
        """Show the translated message for `key` in the active language."""
        self._show(self._t(key))

    # Distinct names so call sites read intentionally, even though Windows
    # renders all three identically.
    def success(self, key: str) -> None:
        self.notify(key)

    def warning(self, key: str) -> None:
        self.notify(key)

    def error(self, key: str) -> None:
        self.notify(key)

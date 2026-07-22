"""
Hotkey-triggered actions.

Every action follows the same template method (`BaseClipboardAction.execute`):

    1. Snapshot whatever is currently on the clipboard (to restore later).
    2. Run `_copy_trigger()` (by default: simulate Ctrl+C on the user's
       existing selection) and race-free wait for the new text to land.
    3. Bail out gracefully if nothing came through / it wasn't text.
    4. Run the action-specific `process()` step.
    5. If the action produces replacement text, write it and simulate Ctrl+V.
    6. Restore the clipboard to its original contents (zero data loss).
    7. Show a toast confirming what happened.

Subclasses only implement `process()` and a couple of class-level constants
— they never touch the clipboard directly, which is what keeps the
race-condition-sensitive logic in exactly one place (`ClipboardManager`).
Ground truth for "what text are we working on" always comes from the
clipboard itself, never from a guess — see `LayoutFixAction` for why that
matters.
"""

from __future__ import annotations

import abc
import logging
import time
import webbrowser
from urllib.parse import quote_plus

from . import input_simulator
from .clipboard_manager import ClipboardError, ClipboardManager
from .config import CLIPBOARD
from .layout_map import LayoutMapper
from .notifier import ToastNotifier

logger = logging.getLogger(__name__)


class BaseClipboardAction(abc.ABC):
    """Template for any hotkey action that reads the current text selection."""

    #: Whether `process()`'s return value should be written back and pasted.
    PASTES_RESULT: bool = True

    #: Friendly name used in toast notifications.
    DISPLAY_NAME: str = "Action"

    def __init__(self, clipboard: ClipboardManager, notifier: ToastNotifier) -> None:
        self._clipboard = clipboard
        self._notifier = notifier

    @abc.abstractmethod
    def process(self, selected_text: str) -> "str | None":
        """
        Transform the selected text. Return the replacement text if this
        action should paste a result (see PASTES_RESULT), or None
        otherwise (e.g. an action that only opens a browser).
        """

    def _capture_text(self) -> "str | None":
        """
        How this action obtains the text to work on. Default: copy
        whatever the user has already manually highlighted. Subclasses
        that must also work with no manual selection (see LayoutFixAction)
        override this to add an automatic-selection fallback.
        """
        return self._clipboard.capture_selection_text(input_simulator.send_copy)

    def execute(self) -> None:
        # A Ctrl-based hotkey fires while Ctrl is still physically down;
        # injecting our own chord before the user lets go would tangle real
        # and synthetic modifier state in the target window.
        input_simulator.wait_for_modifiers_released()

        try:
            original_text = self._clipboard.read_text()
        except ClipboardError:
            logger.exception("Could not snapshot original clipboard before %s.", self.DISPLAY_NAME)
            self._notifier.error("clipboard_busy")
            return

        try:
            selected_text = self._capture_text()
        except ClipboardError:
            logger.exception("Could not read clipboard after copy in %s.", self.DISPLAY_NAME)
            self._notifier.error("clipboard_busy")
            return

        if not selected_text or not selected_text.strip():
            self._notifier.warning("no_selection")
            return

        try:
            result = self.process(selected_text)
        except Exception:
            logger.exception("%s failed while processing selected text.", self.DISPLAY_NAME)
            self._notifier.error("action_failed")
            self._restore_clipboard(original_text)
            return

        if self.PASTES_RESULT and result is not None:
            try:
                self._clipboard.write_text(result)
                time.sleep(CLIPBOARD.PRE_PASTE_DELAY_SECONDS)
                input_simulator.send_paste()
                time.sleep(CLIPBOARD.POST_PASTE_SETTLE_SECONDS)
            except ClipboardError:
                logger.exception("Could not write/paste result in %s.", self.DISPLAY_NAME)
                self._notifier.error("clipboard_busy")

        self._restore_clipboard(original_text)
        self.on_success()

    def _restore_clipboard(self, original_text: "str | None") -> None:
        try:
            if original_text is not None:
                self._clipboard.write_text(original_text)
            else:
                self._clipboard.clear()
        except ClipboardError:
            logger.exception("Failed to restore original clipboard content after %s.", self.DISPLAY_NAME)

    def on_success(self) -> None:
        """Hook for the success toast; overridable for custom messaging."""
        self._notifier.success("layout_fixed")


class LayoutFixAction(BaseClipboardAction):
    """
    [F10] Smart Layout Fixer — works with OR without a manual selection.

    Two-stage capture:
      1. Probe: plain Ctrl+C on a short timeout. If the user *has* already
         highlighted something, that wins — we must never silently discard
         a deliberate selection.
      2. Fallback: nothing was selected, so select the current line back to
         the caret with Shift+Home and copy that. This is what makes "just
         type and hit F10" work with no selecting on the user's part.

    Either way the text we act on is read back from the clipboard rather
    than inferred, so the replacement always matches what is really on
    screen — no character-count guessing, no duplicated fragments.
    """

    DISPLAY_NAME = "Layout Fixer"
    PASTES_RESULT = True

    #: Short probe window — just long enough to detect an existing
    #: selection, short enough that falling back feels instant.
    _PROBE_TIMEOUT_SECONDS = 0.25

    def _capture_text(self) -> "str | None":
        existing = self._clipboard.capture_selection_text(
            input_simulator.send_copy, timeout=self._PROBE_TIMEOUT_SECONDS
        )
        if existing and existing.strip():
            return existing

        def _select_line_and_copy() -> None:
            input_simulator.send_select_to_line_start()
            input_simulator.send_copy()

        return self._clipboard.capture_selection_text(_select_line_and_copy)

    def process(self, selected_text: str) -> str:
        return LayoutMapper.convert(selected_text)

    def on_success(self) -> None:
        self._notifier.success("layout_fixed")


class SmartSearchAction(BaseClipboardAction):
    """[Ctrl+G] Opens the default browser with a Google search for the selection."""

    DISPLAY_NAME = "Smart Search"
    PASTES_RESULT = False

    def process(self, selected_text: str) -> None:
        url = f"https://www.google.com/search?q={quote_plus(selected_text)}"
        webbrowser.open(url)
        return None

    def on_success(self) -> None:
        self._notifier.success("searching")


class QuickTranslateAction(BaseClipboardAction):
    """[Ctrl+T] Opens Google Translate (auto-detect -> auto) for the selection."""

    DISPLAY_NAME = "Quick Translate"
    PASTES_RESULT = False

    def process(self, selected_text: str) -> None:
        encoded = quote_plus(selected_text)
        url = f"https://translate.google.com/?sl=auto&tl=auto&text={encoded}&op=translate"
        webbrowser.open(url)
        return None

    def on_success(self) -> None:
        self._notifier.success("translating")

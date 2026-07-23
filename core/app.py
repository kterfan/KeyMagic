"""
Application orchestrator: wires hotkeys -> actions, owns pause state and
user settings, and hosts the tray icon's blocking run loop.
"""

from __future__ import annotations

import logging
import threading

from . import startup
from .actions import LayoutFixAction, QuickTranslateAction, SmartSearchAction
from .clipboard_manager import ClipboardManager
from .config import HOTKEYS, HotkeyBinding
from .flyout import FlyoutController
from .hotkey_listener import HotkeyListener
from .i18n import Translator
from .notifier import ToastNotifier
from .settings import Settings
from .tray import TrayApplication

logger = logging.getLogger(__name__)


class KeyMagicApp:
    """
    Top-level controller.

    Global hotkeys are claimed at OS level (see `HotkeyListener`) and
    dispatched to Action instances on their own worker threads, so a slow
    browser launch or a clipboard retry never stalls the hotkey message
    loop. Pause/resume lets the user disable every hotkey from the flyout
    without exiting.
    """

    def __init__(self) -> None:
        self.settings = Settings.load()
        self._translator = Translator(self.settings.language)
        self._clipboard = ClipboardManager()
        self._notifier = ToastNotifier(self.settings, self._translator)
        self._paused = threading.Event()  # set() == paused
        self._listener = HotkeyListener()

        # Reconcile the registry with the stored preference on every start:
        # the user may have removed the entry via Windows' Startup Apps UI,
        # or the app may have been reinstalled to a different path.
        startup.apply(self.settings.autostart)

        self._bindings: list[tuple[HotkeyBinding, object]] = [
            (HOTKEYS.LAYOUT_FIX, LayoutFixAction(self._clipboard, self._notifier)),
            (HOTKEYS.SMART_SEARCH, SmartSearchAction(self._clipboard, self._notifier)),
            (HOTKEYS.QUICK_TRANSLATE, QuickTranslateAction(self._clipboard, self._notifier)),
        ]

        self._flyout = FlyoutController(
            translator=self._translator,
            is_paused=self.is_paused,
            on_toggle_pause=self.toggle_pause,
            on_toggle_mute=self.toggle_mute,
            on_toggle_autostart=self.toggle_autostart,
            on_toggle_language=self.toggle_language,
            on_exit=self.request_exit,
            get_settings=lambda: self.settings,
        )

        self._tray = TrayApplication(
            translator=self._translator,
            is_paused=self.is_paused,
            on_open_panel=self._flyout.show_panel,
            on_open_about=self._flyout.show_about,
            on_exit=self.shutdown,
        )

        # Re-entrancy guard: one lock per action, so a still-running action
        # can't be overlapped by a fresh trigger. (Held-key auto-repeat is
        # already suppressed at OS level by MOD_NOREPEAT.)
        self._busy_locks: dict[str, threading.Lock] = {
            binding.label: threading.Lock() for binding, _ in self._bindings
        }

    # ------------------------------------------------------------- app state
    def is_paused(self) -> bool:
        return self._paused.is_set()

    def toggle_pause(self) -> None:
        if self._paused.is_set():
            self._paused.clear()
            logger.info("KeyMagic resumed.")
            self._notifier.success("resumed")
        else:
            self._paused.set()
            logger.info("KeyMagic paused.")
            self._notifier.warning("paused")
        self._tray.refresh()

    def toggle_mute(self) -> None:
        self.settings.muted = not self.settings.muted
        self.settings.save()
        logger.info("Notification sound %s.", "muted" if self.settings.muted else "unmuted")

    def toggle_autostart(self) -> None:
        self.settings.autostart = not self.settings.autostart
        startup.apply(self.settings.autostart)
        self.settings.save()

    def toggle_language(self) -> None:
        self.settings.language = "fa" if self.settings.language == "en" else "en"
        self._translator.set_language(self.settings.language)
        self.settings.save()
        self._tray.refresh()
        logger.info("Language switched to %s.", self.settings.language)

    def request_exit(self) -> None:
        """Exit requested from the flyout: stop the tray, which ends run()."""
        self.shutdown()
        self._tray.stop()

    # ----------------------------------------------------------- dispatching
    def _dispatch(self, label: str, action: object) -> None:
        """
        Hotkey callback (runs on the listener's message-loop thread): skip
        while paused, skip if this action is already running, otherwise
        hand off to a worker thread so the message loop stays responsive.
        """
        if self._paused.is_set():
            return

        lock = self._busy_locks[label]
        if not lock.acquire(blocking=False):
            return  # previous run of this hotkey hasn't finished yet

        threading.Thread(target=self._safe_execute, args=(action, lock), daemon=True).start()

    @staticmethod
    def _safe_execute(action: object, lock: threading.Lock) -> None:
        try:
            action.execute()
        except Exception:
            # Last-resort guard: an action should already handle its own
            # errors, but a worker thread must never die silently or crash
            # the process on an unexpected exception.
            logger.exception("Unhandled exception while executing %s.", action.DISPLAY_NAME)
        finally:
            lock.release()

    def _register_hotkeys(self) -> None:
        for binding, action in self._bindings:
            self._listener.register(
                binding.label,
                binding.modifiers,
                binding.virtual_key,
                lambda label=binding.label, act=action: self._dispatch(label, act),
            )
        self._listener.start()

    def open_panel(self) -> None:
        """Surface the control panel. Used when a second launch hands off here."""
        self._flyout.show_panel()

    # -------------------------------------------------------------- lifecycle
    def shutdown(self) -> None:
        logger.info("Shutting down KeyMagic.")
        self._listener.stop()
        self._flyout.stop()

    def run(self) -> None:
        """Starts subsystems, then blocks the main thread running the tray icon."""
        self._flyout.start()
        self._register_hotkeys()
        self._notifier.success("running")
        self._tray.run()

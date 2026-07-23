"""
The control-centre flyout — a modern, Apple-style panel that opens near the
clock instead of a plain grey Win32 context menu.

Why build a window instead of using the tray menu
--------------------------------------------------
`pystray` menus are native Win32 popup menus. They cannot be styled: no
rounded corners, no custom typography, no toggle switches, no right-to-left
mirroring beyond what the OS does for the whole shell. Since the brief is a
panel that feels like macOS Control Centre and must flip to RTL in Persian,
the panel is drawn as a borderless always-on-top Tk window positioned just
above the notification area.

Tk specifics worth knowing
---------------------------
* Tk is not thread-safe and every app has exactly one main loop. The tray
  icon already owns the process's main thread, so this module runs its own
  Tk loop on a dedicated thread and marshals every open request onto it.
* `overrideredirect(True)` removes the title bar and border, which is what
  makes it read as a flyout rather than a dialog.
* Rounded corners come from the DWM window-attribute API on Windows 11;
  on Windows 10 the call fails harmlessly and the panel is square.
"""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
import tkinter as tk
import webbrowser
from ctypes import wintypes
from typing import Callable, Optional

from .config import UI
from .i18n import Translator

logger = logging.getLogger(__name__)

GITHUB_URL = "https://github.com/kterfan/KeyMagic"
AUTHOR = "Erfan Esmailzadeh"

# --- Palette (dark, translucent-looking, macOS-ish) ------------------------
_BG = "#1c1c1e"
_BG_ELEVATED = "#2c2c2e"
_BG_HOVER = "#3a3a3c"
_TEXT = "#f5f5f7"
_TEXT_DIM = "#98989d"
# Sampled from the application artwork (assets/icon-source.png) so the panel
# and the tray icon that opens it share one palette.
_ACCENT = "#d66a3e"
_SEPARATOR = "#38383a"

_PANEL_WIDTH = 320
_PAD = 16

# Latin and Persian need different faces; Segoe UI has poor Persian shaping,
# while Tahoma/Segoe UI both ship with Windows and Tahoma renders Farsi well.
_FONT_LATIN = "Segoe UI"
_FONT_PERSIAN = "Tahoma"

# DWM attribute ids for the Windows 11 rounded-corner API.
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_ROUND = 2


def _apply_rounded_corners(window: tk.Misc) -> None:
    """Ask DWM for rounded corners (Windows 11); silently no-op elsewhere."""
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        preference = ctypes.c_int(_DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_int(_DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
    except Exception:
        logger.debug("Rounded corners unavailable on this Windows build.", exc_info=True)


class _Row(tk.Frame):
    """One interactive line in the panel, with hover feedback."""

    def __init__(self, parent, text: str, translator: Translator, on_click: Callable[[], None],
                 accessory: str = "", dim: bool = False):
        super().__init__(parent, bg=_BG_ELEVATED, cursor="hand2")
        rtl = translator.is_rtl
        family = _FONT_PERSIAN if rtl else _FONT_LATIN

        self._label = tk.Label(
            self, text=text, bg=_BG_ELEVATED, fg=_TEXT_DIM if dim else _TEXT,
            font=(family, 10), anchor="e" if rtl else "w", padx=12, pady=9,
        )
        self._accessory = tk.Label(
            self, text=accessory, bg=_BG_ELEVATED, fg=_ACCENT,
            font=(family, 10, "bold"), padx=12,
        )

        # In RTL the label hugs the right edge and the accessory the left.
        if rtl:
            self._accessory.pack(side="left")
            self._label.pack(side="right", fill="x", expand=True)
        else:
            self._label.pack(side="left", fill="x", expand=True)
            self._accessory.pack(side="right")

        for widget in (self, self._label, self._accessory):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", lambda _event: on_click())

    def _paint(self, colour: str) -> None:
        for widget in (self, self._label, self._accessory):
            widget.configure(bg=colour)

    def _on_enter(self, _event) -> None:
        self._paint(_BG_HOVER)

    def _on_leave(self, _event) -> None:
        self._paint(_BG_ELEVATED)


class FlyoutController:
    """
    Owns the Tk thread and builds the two panels (control centre + about).

    All public methods are safe to call from any thread: they enqueue work
    that the Tk loop picks up, because touching widgets from another thread
    corrupts Tk's internal state.
    """

    def __init__(
        self,
        translator: Translator,
        is_paused: Callable[[], bool],
        on_toggle_pause: Callable[[], None],
        on_toggle_mute: Callable[[], None],
        on_toggle_autostart: Callable[[], None],
        on_toggle_language: Callable[[], None],
        on_exit: Callable[[], None],
        get_settings: Callable[[], object],
    ) -> None:
        self._t = translator
        self._is_paused = is_paused
        self._on_toggle_pause = on_toggle_pause
        self._on_toggle_mute = on_toggle_mute
        self._on_toggle_autostart = on_toggle_autostart
        self._on_toggle_language = on_toggle_language
        self._on_exit = on_exit
        self._get_settings = get_settings

        self._root: Optional[tk.Tk] = None
        self._window: Optional[tk.Toplevel] = None
        self._requests: "queue.Queue[str]" = queue.Queue()
        self._ready = threading.Event()

    # ---------------------------------------------------------------- public
    def start(self) -> None:
        threading.Thread(target=self._run_tk, daemon=True, name="Flyout").start()
        self._ready.wait(timeout=5.0)

    def show_panel(self) -> None:
        self._requests.put("panel")

    def show_about(self) -> None:
        self._requests.put("about")

    def stop(self) -> None:
        self._requests.put("quit")

    # ------------------------------------------------------------- internals
    def _run_tk(self) -> None:
        self._root = tk.Tk()
        self._root.withdraw()  # the real UI lives in Toplevels
        self._ready.set()
        self._poll_requests()
        self._root.mainloop()

    def _poll_requests(self) -> None:
        """Drain cross-thread requests on the Tk loop, ~20x/second."""
        try:
            while True:
                request = self._requests.get_nowait()
                if request == "panel":
                    self._build_window(self._populate_panel)
                elif request == "about":
                    self._build_window(self._populate_about)
                elif request == "quit":
                    if self._root is not None:
                        self._root.quit()
                    return
        except queue.Empty:
            pass
        if self._root is not None:
            self._root.after(50, self._poll_requests)

    def _close(self) -> None:
        if self._window is not None:
            self._window.destroy()
            self._window = None

    def _build_window(self, populate: Callable[[tk.Toplevel], None]) -> None:
        self._close()

        window = tk.Toplevel(self._root)
        self._window = window
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=_BG)

        container = tk.Frame(window, bg=_BG, highlightthickness=1, highlightbackground=_SEPARATOR)
        container.pack(fill="both", expand=True)
        populate(container)

        window.update_idletasks()
        self._position_near_tray(window)
        _apply_rounded_corners(window)

        window.bind("<Escape>", lambda _e: self._close())
        window.focus_force()

        # Dismiss-on-click-away is bound only after the window has settled.
        # Binding it immediately makes the panel close itself: focus bounces
        # between the shell and the new window during creation, which fires
        # <FocusOut> before the user has seen anything.
        window.after(500, lambda: window.bind("<FocusOut>", lambda _e: self._close()))

    def _position_near_tray(self, window: tk.Toplevel) -> None:
        """
        Anchor the panel above the notification area, inset from the screen
        edge — the position users expect for a tray flyout.
        """
        width = window.winfo_width()
        height = window.winfo_height()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()

        margin = 12
        taskbar_allowance = 60  # keeps the panel clear of the taskbar
        x = screen_w - width - margin
        y = screen_h - height - taskbar_allowance
        window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    # ------------------------------------------------------------- rendering
    def _header(self, parent: tk.Frame, subtitle: str) -> None:
        rtl = self._t.is_rtl
        family = _FONT_PERSIAN if rtl else _FONT_LATIN
        anchor = "e" if rtl else "w"

        header = tk.Frame(parent, bg=_BG, padx=_PAD, pady=14)
        header.pack(fill="x")

        title = tk.Label(
            header, text=UI.APP_NAME, bg=_BG, fg=_TEXT,
            font=(_FONT_LATIN, 16, "bold"), anchor=anchor,
        )
        title.pack(fill="x")

        tk.Label(
            header, text=subtitle, bg=_BG, fg=_TEXT_DIM,
            font=(family, 9), anchor=anchor, justify="right" if rtl else "left",
            wraplength=_PANEL_WIDTH - 2 * _PAD,
        ).pack(fill="x", pady=(2, 0))

        tk.Frame(parent, bg=_SEPARATOR, height=1).pack(fill="x")

    def _populate_panel(self, parent: tk.Frame) -> None:
        t = self._t
        settings = self._get_settings()
        paused = self._is_paused()

        parent.configure(width=_PANEL_WIDTH)
        self._header(parent, t("status_paused") if paused else t("status_active"))

        body = tk.Frame(parent, bg=_BG_ELEVATED, pady=6)
        body.pack(fill="both", expand=True)

        def row(text: str, handler: Callable[[], None], accessory: str = "") -> None:
            _Row(body, text, t, handler, accessory=accessory).pack(fill="x", padx=6, pady=1)

        # A filled dot reads as "on" at a glance without needing a real
        # switch widget, which Tk does not provide.
        def toggle_mark(enabled: bool) -> str:
            return "●" if enabled else "○"

        row(t("resume") if paused else t("pause"), self._act(self._on_toggle_pause))
        row(t("mute_sound"), self._act(self._on_toggle_mute), toggle_mark(getattr(settings, "muted", False)))
        row(t("show_toasts"), self._act(self._toggle_toasts), toggle_mark(getattr(settings, "show_toasts", True)))
        row(t("autostart"), self._act(self._on_toggle_autostart), toggle_mark(getattr(settings, "autostart", True)))
        row(t("language"), self._act(self._on_toggle_language), "فارسی" if not t.is_rtl else "English")

        tk.Frame(body, bg=_SEPARATOR, height=1).pack(fill="x", pady=6, padx=12)

        row(t("about"), lambda: self._requests.put("about"))
        row(t("exit"), self._act(self._on_exit))

    def _populate_about(self, parent: tk.Frame) -> None:
        t = self._t
        rtl = t.is_rtl
        family = _FONT_PERSIAN if rtl else _FONT_LATIN
        anchor = "e" if rtl else "w"

        parent.configure(width=_PANEL_WIDTH)
        self._header(parent, t("about_tagline"))

        body = tk.Frame(parent, bg=_BG_ELEVATED, padx=_PAD, pady=14)
        body.pack(fill="both", expand=True)

        def field(label: str, value: str, value_colour: str = _TEXT) -> tk.Label:
            line = tk.Frame(body, bg=_BG_ELEVATED)
            line.pack(fill="x", pady=3)
            key_label = tk.Label(line, text=label, bg=_BG_ELEVATED, fg=_TEXT_DIM, font=(family, 9))
            value_label = tk.Label(line, text=value, bg=_BG_ELEVATED, fg=value_colour, font=(family, 10, "bold"))
            if rtl:
                key_label.pack(side="right")
                value_label.pack(side="right", padx=(0, 8))
            else:
                key_label.pack(side="left")
                value_label.pack(side="left", padx=(8, 0))
            return value_label

        field(t("created_by"), AUTHOR)
        field(t("version"), UI.VERSION)

        tk.Frame(body, bg=_SEPARATOR, height=1).pack(fill="x", pady=10)

        tk.Label(
            body, text=t("shortcuts"), bg=_BG_ELEVATED, fg=_TEXT_DIM,
            font=(family, 9), anchor=anchor,
        ).pack(fill="x", pady=(0, 6))

        for combo, key in (("F10", "fix_layout"), ("Ctrl + G", "smart_search"), ("Ctrl + T", "quick_translate")):
            line = tk.Frame(body, bg=_BG_ELEVATED)
            line.pack(fill="x", pady=2)
            combo_label = tk.Label(
                line, text=combo, bg=_BG, fg=_ACCENT, font=(_FONT_LATIN, 9, "bold"), padx=8, pady=2,
            )
            text_label = tk.Label(line, text=t(key), bg=_BG_ELEVATED, fg=_TEXT, font=(family, 9))
            if rtl:
                combo_label.pack(side="right")
                text_label.pack(side="right", padx=(0, 10))
            else:
                combo_label.pack(side="left")
                text_label.pack(side="left", padx=(10, 0))

        tk.Frame(body, bg=_SEPARATOR, height=1).pack(fill="x", pady=10)

        link = tk.Label(
            body, text="github.com/kterfan/KeyMagic", bg=_BG_ELEVATED, fg=_ACCENT,
            font=(_FONT_LATIN, 9, "underline"), cursor="hand2", anchor=anchor,
        )
        link.pack(fill="x")
        link.bind("<Button-1>", lambda _e: webbrowser.open(GITHUB_URL))

        close = _Row(body, t("close"), t, self._close)
        close.pack(fill="x", pady=(14, 0))

    def _act(self, handler: Callable[[], None]) -> Callable[[], None]:
        """Run a menu action, then close the panel — standard flyout behaviour."""

        def wrapped() -> None:
            handler()
            self._close()

        return wrapped

    def _toggle_toasts(self) -> None:
        settings = self._get_settings()
        settings.show_toasts = not settings.show_toasts
        settings.save()

"""
System tray integration.

The tray icon's own menu is deliberately minimal: a default action that
opens the rich flyout panel (see `core.flyout`), plus native fallbacks.
Native Win32 menus cannot be styled at all, so everything visual lives in
the flyout — but keeping About/Exit here too means the app stays usable and
quittable even if the Tk panel ever fails to appear.
"""

from __future__ import annotations

import logging
from typing import Callable

import pystray

from .config import UI
from .i18n import Translator
from .icon import build_icon

logger = logging.getLogger(__name__)

# Rendered once per state rather than on every menu interaction — the
# supersampled draw is cheap but not free, and the images never change.
_ICON_CACHE: dict[bool, object] = {}


def _icon_for(paused: bool):
    if paused not in _ICON_CACHE:
        _ICON_CACHE[paused] = build_icon(paused=paused, size=64)
    return _ICON_CACHE[paused]


class TrayApplication:
    """Owns the pystray.Icon instance and routes clicks to the flyout."""

    def __init__(
        self,
        translator: Translator,
        is_paused: Callable[[], bool],
        on_open_panel: Callable[[], None],
        on_open_about: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._t = translator
        self._is_paused = is_paused
        self._on_open_panel = on_open_panel
        self._on_open_about = on_open_about
        self._on_exit = on_exit

        self._icon = pystray.Icon(
            UI.APP_NAME,
            icon=_icon_for(paused=False),
            title=f"{UI.APP_NAME} {UI.VERSION}",
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            # `default=True` makes a plain left-click open the panel, which
            # is what makes the flyout feel like part of the shell rather
            # than a dialog you have to hunt through a menu for.
            pystray.MenuItem(UI.APP_NAME, self._handle_open_panel, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _i: self._t("about"), self._handle_open_about),
            pystray.MenuItem(lambda _i: self._t("exit"), self._handle_exit),
        )

    def _handle_open_panel(self, _icon=None, _item=None) -> None:
        self._on_open_panel()

    def _handle_open_about(self, _icon=None, _item=None) -> None:
        self._on_open_about()

    def _handle_exit(self, icon: pystray.Icon, _item=None) -> None:
        self._on_exit()
        icon.stop()

    def refresh(self) -> None:
        """Repaint the icon and menu after a state or language change."""
        self._icon.icon = _icon_for(paused=self._is_paused())
        self._icon.update_menu()

    def stop(self) -> None:
        """Tear the tray icon down, which unblocks `run()` on the main thread."""
        self._icon.stop()

    def run(self) -> None:
        """Blocking call — must run on the main thread."""
        self._icon.run()

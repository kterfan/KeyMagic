"""
Persisted user preferences.

Stored as JSON under %APPDATA%\\KeyMagic\\settings.json rather than beside
the executable, so the app keeps working when installed to Program Files
(which is not user-writable) and each Windows user gets their own settings.

Every read is defensive: a corrupt, hand-edited, or partially-written file
must never prevent the app from starting, so unparseable content falls back
to defaults instead of raising.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields

logger = logging.getLogger(__name__)

_SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KeyMagic")
_SETTINGS_PATH = os.path.join(_SETTINGS_DIR, "settings.json")


@dataclass
class Settings:
    """User-facing preferences. Field names are the JSON keys."""

    language: str = "en"        # "en" or "fa"
    muted: bool = False         # suppress the toast notification *sound*
    show_toasts: bool = True    # suppress toasts entirely
    autostart: bool = True      # launch with Windows (default on, per spec)

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return cls()
        except (json.JSONDecodeError, OSError):
            logger.exception("settings.json unreadable — falling back to defaults.")
            return cls()

        # Only accept keys we actually define, so an old or tampered file
        # can't inject unexpected attributes.
        known = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})

    def save(self) -> None:
        try:
            os.makedirs(_SETTINGS_DIR, exist_ok=True)
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as handle:
                json.dump(asdict(self), handle, indent=2)
        except OSError:
            logger.exception("Could not persist settings — continuing with in-memory values.")

    @property
    def is_persian(self) -> bool:
        return self.language == "fa"

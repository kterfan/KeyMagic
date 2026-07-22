"""
Bilingual (English / Persian) user-facing strings.

Kept in one table so every visible string has both variants side by side —
adding a new message without its translation becomes obvious at a glance,
and nothing user-facing is hardcoded elsewhere in the app.
"""

from __future__ import annotations

from typing import Dict

# key -> {"en": ..., "fa": ...}
_STRINGS: Dict[str, Dict[str, str]] = {
    # Toasts
    "running": {
        "en": "Running in the background",
        "fa": "در پس‌زمینه در حال اجراست",
    },
    "layout_fixed": {"en": "Language fixed!", "fa": "زبان اصلاح شد!"},
    "searching": {"en": "Searching Google…", "fa": "در حال جست‌وجو در گوگل…"},
    "translating": {"en": "Opening Google Translate…", "fa": "گوگل ترنسلیت باز می‌شود…"},
    "no_selection": {"en": "No text selected", "fa": "متنی انتخاب نشده است"},
    "clipboard_busy": {"en": "Clipboard is busy — try again", "fa": "کلیپ‌بورد مشغول است — دوباره تلاش کنید"},
    "action_failed": {"en": "Action failed — see log", "fa": "عملیات ناموفق بود — گزارش را ببینید"},
    "paused": {"en": "Paused", "fa": "متوقف شد"},
    "resumed": {"en": "Resumed", "fa": "از سر گرفته شد"},
    # Tray / flyout
    "pause": {"en": "Pause", "fa": "توقف"},
    "resume": {"en": "Resume", "fa": "ادامه"},
    "about": {"en": "About", "fa": "درباره"},
    "exit": {"en": "Exit", "fa": "خروج"},
    "settings": {"en": "Settings", "fa": "تنظیمات"},
    "mute_sound": {"en": "Mute notification sound", "fa": "بی‌صدا کردن اعلان‌ها"},
    "show_toasts": {"en": "Show notifications", "fa": "نمایش اعلان‌ها"},
    "autostart": {"en": "Start with Windows", "fa": "اجرا هنگام شروع ویندوز"},
    "language": {"en": "Language", "fa": "زبان"},
    "status_active": {"en": "Active", "fa": "فعال"},
    "status_paused": {"en": "Paused", "fa": "متوقف"},
    # About window
    "about_tagline": {
        "en": "Fix wrong-layout typing anywhere on Windows",
        "fa": "اصلاح متن تایپ‌شده با چیدمان اشتباه، در هر برنامه‌ای",
    },
    "created_by": {"en": "Created by", "fa": "ساخته‌شده توسط"},
    "version": {"en": "Version", "fa": "نسخه"},
    "shortcuts": {"en": "Shortcuts", "fa": "کلیدهای میان‌بر"},
    "fix_layout": {"en": "Fix keyboard layout", "fa": "اصلاح چیدمان کیبورد"},
    "smart_search": {"en": "Search on Google", "fa": "جست‌وجو در گوگل"},
    "quick_translate": {"en": "Translate text", "fa": "ترجمهٔ متن"},
    "close": {"en": "Close", "fa": "بستن"},
}


class Translator:
    """Resolves message keys for the currently selected language."""

    def __init__(self, language: str = "en") -> None:
        self.language = language

    def set_language(self, language: str) -> None:
        self.language = language

    @property
    def is_rtl(self) -> bool:
        """True when the active language renders right-to-left."""
        return self.language == "fa"

    def __call__(self, key: str) -> str:
        """Translate `key`, falling back to English, then to the key itself."""
        entry = _STRINGS.get(key)
        if entry is None:
            return key
        return entry.get(self.language) or entry.get("en", key)

"""
Bi-directional English (QWERTY) <-> Persian (standard Iranian layout) keymap.

The mapping below reflects physical key position, not meaning: it maps each
English QWERTY key to the character produced by the same physical key on
the standard Iranian Persian keyboard layout used by Windows. This is what
lets us "fix" text that was typed with the wrong active layout — the user's
keystrokes landed on the right *keys*, just the wrong *characters*.
"""

from __future__ import annotations

import re

# Physical-key letter/punctuation row mapping (unshifted).
_EN_TO_FA_BASE = {
    "q": "ض", "w": "ص", "e": "ث", "r": "ق", "t": "ف", "y": "غ",
    "u": "ع", "i": "ه", "o": "خ", "p": "ح", "[": "ج", "]": "چ",
    "a": "ش", "s": "س", "d": "ی", "f": "ب", "g": "ل", "h": "ا",
    "j": "ت", "k": "ن", "l": "م", ";": "ک", "'": "گ",
    "z": "ظ", "x": "ط", "c": "ز", "v": "ر", "b": "ذ", "n": "د",
    "m": "پ", ",": "و", ".": "،", "/": ".",
}

# Digit row: standard layout produces Persian (Eastern Arabic-Indic) digits.
_EN_TO_FA_DIGITS = {
    "1": "۱", "2": "۲", "3": "۳", "4": "۴", "5": "۵",
    "6": "۶", "7": "۷", "8": "۸", "9": "۹", "0": "۰",
}

# Shifted symbol row commonly produced on the Persian layout.
_EN_TO_FA_SHIFTED = {
    "!": "!", "@": "٬", "#": "٫", "$": "﷼", "%": "٪",
    "^": "×", "&": "،", "*": "*", "(": ")", ")": "(",
    "Q": "ض", "W": "ص", "E": "ث", "R": "ق", "T": "ف", "Y": "غ",
    "U": "ع", "I": "ه", "O": "خ", "P": "ح", "{": "ج", "}": "چ",
    "A": "ش", "S": "س", "D": "ی", "F": "ب", "G": "ل", "H": "ا",
    "J": "ت", "K": "ن", "L": "م", ":": "ک", '"': "گ",
    "Z": "ظ", "X": "ط", "C": "ز", "V": "ر", "B": "ذ", "N": "د",
    "M": "پ", "<": "و", ">": "،", "?": ".",
}

_EN_TO_FA = {**_EN_TO_FA_BASE, **_EN_TO_FA_DIGITS, **_EN_TO_FA_SHIFTED}

# Reverse direction: several English keys map to the same Persian character
# (e.g. both `q` and `Q` produce «ض»), so build the inverse from the base
# and digit tables only. Those hold the canonical lowercase/unshifted key
# for each Persian character, which is what a user actually wants typed
# back. Iterating the shifted table too would overwrite these with capitals.
_FA_TO_EN = {fa: en for en, fa in {**_EN_TO_FA_BASE, **_EN_TO_FA_DIGITS}.items()}

# Precomputed translation tables. `str.translate` walks the string once in
# C with an integer-keyed lookup, which is markedly faster than building a
# list of characters through per-character dict `.get()` calls in Python —
# and it is the idiomatic way to express "map these characters to those".
_EN_TO_FA_TABLE = str.maketrans(_EN_TO_FA)
_FA_TO_EN_TABLE = str.maketrans(_FA_TO_EN)

_PERSIAN_ARABIC_BLOCK = re.compile(r"[؀-ۿ]")
_LATIN_BLOCK = re.compile(r"[A-Za-z]")


class LayoutMapper:
    """Detects dominant script and converts text to the opposite keyboard layout."""

    @staticmethod
    def detect_dominant_script(text: str) -> str:
        """
        Return "fa" if Persian/Arabic-script letters dominate the text,
        "en" if Latin letters dominate, or "unknown" if neither is present.
        """
        persian_count = len(_PERSIAN_ARABIC_BLOCK.findall(text))
        latin_count = len(_LATIN_BLOCK.findall(text))

        if persian_count == 0 and latin_count == 0:
            return "unknown"
        return "fa" if persian_count >= latin_count else "en"

    @staticmethod
    def convert(text: str) -> str:
        """
        Convert `text` to the opposite keyboard layout based on its
        detected dominant script. Characters with no mapping (spaces,
        digits already in the target script, emoji, etc.) pass through
        unchanged.
        """
        dominant = LayoutMapper.detect_dominant_script(text)

        if dominant == "en":
            return text.translate(_EN_TO_FA_TABLE)
        if dominant == "fa":
            return text.translate(_FA_TO_EN_TABLE)
        return text

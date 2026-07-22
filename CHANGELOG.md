# Changelog · تاریخچهٔ تغییرات

All notable changes to KeyMagic are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

همهٔ تغییرات مهم KeyMagic در این فایل ثبت می‌شود.

---

## [1.0.1] — 2026-07-22

Two bugs, both caused by the app requiring administrator rights. Upgrading from 1.0.0 is recommended.

### Fixed

- **Setup failed at the end with `CreateProcess failed; code 740`.**
  Inno Setup's launch step used `CreateProcess`, which cannot satisfy a `requireAdministrator` manifest, so the installer could not start the app it had just installed. Now routed through `ShellExecute` via the `shellexec` flag.

- **"Start with Windows" silently did nothing.**
  The setting wrote an `HKCU\...\Run` entry, but Windows skips Run-key entries that would need an elevation prompt at logon — no error, no prompt, no app. The checkbox was on and the registry value was present, so the feature looked implemented while never once starting the app. Replaced with a Task Scheduler entry at `RunLevel: HIGHEST`, the supported mechanism for launching an elevated program at logon. Legacy Run-key values are cleaned up on upgrade and on uninstall.

### Documentation

- Explained the "Windows protected your PC" SmartScreen warning in both languages, with the dialog pictured and the correct button marked.
- Documented **Unblock** (Properties → Unblock, or `Unblock-File`) as the cleaner alternative to *Run anyway*, including why it works — SmartScreen only evaluates files carrying the Mark of the Web.
- Published `SHA256SUMS.txt` with each release so downloads can be verified.

---

## [1.0.0] — 2026-07-22

First public release.

### Added

- **Smart Layout Fixer** (<kbd>F10</kbd>) — rewrites text typed with the wrong keyboard layout, English ⇄ Persian. Works on a selection, or auto-selects the current line when nothing is selected. Script detection is automatic and bidirectional.
- **Smart Search** (<kbd>Ctrl</kbd>+<kbd>G</kbd>) — URL-encodes the selected text and opens Google in the default browser.
- **Quick Translate** (<kbd>Ctrl</kbd>+<kbd>T</kbd>) — opens Google Translate with auto source-language detection.
- **Control panel** in the system tray — a custom flyout rather than a Win32 menu, with full right-to-left mirroring in Persian.
- **About page** showing author, version, shortcuts and project link.
- Settings for notification sound, notification visibility, autostart and interface language, persisted to `%APPDATA%\KeyMagic\settings.json`.
- Bilingual (English / Persian, RTL) Inno Setup installer and a WiX MSI for managed deployment.
- Procedurally drawn 3D keycap icon — no binary art assets in the repository.

### Technical notes

- Global hotkeys use the native Win32 **`RegisterHotKey`** API instead of a keyboard-hook library. The hook approach broke subtly: suppressing combinations requires buffering every <kbd>Ctrl</kbd> press, which also caught the app's own synthetic <kbd>Ctrl</kbd>+<kbd>C</kbd> and released the pieces out of order, delivering a bare `c` to the target window. It surfaced as `sghl` + <kbd>F10</kbd> producing `سلامز` — the trailing `ز` being exactly `c` run through the layout map.
- Clipboard reads synchronise on the **OS clipboard sequence number** rather than a fixed sleep, which removes the race entirely. The user's original clipboard contents are always restored.
- Key events are injected via **`SendInput`** with real hardware scan codes resolved through `MapVirtualKeyW`, so applications that reject virtual-key-only input still accept them.
- The app self-elevates: Windows UIPI blocks synthetic input from a lower-integrity process to an elevated window, so running elevated is what makes "works everywhere" true.

[1.0.1]: https://github.com/kterfan/KeyMagic/releases/tag/v1.0.1
[1.0.0]: https://github.com/kterfan/KeyMagic/releases/tag/v1.0.0

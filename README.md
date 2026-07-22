<div align="center">

<img src="assets/icon.png" width="128" alt="KeyMagic">

# KeyMagic

**Fix wrong-layout typing anywhere on Windows.**
**اصلاح متن تایپ‌شده با چیدمان اشتباه، در هر برنامه‌ای**

[![Release](https://img.shields.io/github/v/release/kterfan/KeyMagic?style=flat-square&color=7c5cff)](https://github.com/kterfan/KeyMagic/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/kterfan/KeyMagic/total?style=flat-square&color=7c5cff)](https://github.com/kterfan/KeyMagic/releases)
[![License](https://img.shields.io/badge/license-MIT-7c5cff?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-7c5cff?style=flat-square)](https://github.com/kterfan/KeyMagic/releases)

### [⬇️ Download for Windows](https://github.com/kterfan/KeyMagic/releases/latest)

**English** · [فارسی](#-فارسی)

</div>

---

## The problem

You start typing a message in Persian, but the keyboard is still on English:

```
سلام چطوری   →   sghl ]xdvd
```

Now you delete it and retype the whole thing. Every day. In every app.

**KeyMagic fixes it with one key.** Select nothing, press <kbd>F10</kbd>, and the
text you just typed is rewritten in the correct layout — in place, in whatever
application you were already in.

```
sghl ]xdvd   →   سلام چطوری          [F10]
lk kld n,kl  →   من نمی دونم         [F10]
```

It works both ways. Persian typed on an English layout, English typed on a
Persian layout — same key, same result.

---

## Features

| Shortcut | What it does |
|:--|:--|
| <kbd>F10</kbd> | **Smart Layout Fixer** — converts the selected text, or the current line if nothing is selected |
| <kbd>Ctrl</kbd>+<kbd>G</kbd> | **Smart Search** — Google-searches the selected text in your default browser |
| <kbd>Ctrl</kbd>+<kbd>T</kbd> | **Quick Translate** — opens Google Translate with the selected text |

- **Works everywhere** — Word, Chrome, Telegram, VS Code, terminals, even elevated apps
- **Never loses your clipboard** — whatever you had copied is restored afterwards
- **Silent by default** — runs in the tray with no window; mute the notification sound entirely if you like
- **Bilingual UI** — English and Persian, with full right-to-left mirroring
- **Starts with Windows** — on by default, one click to turn off, always quittable

<div align="center">
<img src="assets/screenshots/panel-en.png" width="300" alt="Control panel">
&nbsp;&nbsp;
<img src="assets/screenshots/panel-fa.png" width="277" alt="Persian control panel (RTL)">
<br><em>Click the tray icon for the control panel — it mirrors to RTL in Persian</em>
</div>

---

## Install

Download the latest installer and run it:

**[⬇️ KeyMagic-Setup.exe](https://github.com/kterfan/KeyMagic/releases/latest)** — the normal choice.
Bilingual wizard, asks for English or Persian on the first screen.

**[⬇️ KeyMagic.msi](https://github.com/kterfan/KeyMagic/releases/latest)** — for
deploying via Group Policy, Intune or SCCM.

> **Windows may warn you** that the publisher is unknown. That is expected —
> the installer is not code-signed, because a certificate costs a few hundred
> dollars a year. Click **More info → Run anyway**. You can verify the build
> yourself by cloning this repo and running `python build.py`.

**Requirements:** Windows 10 or 11 (64-bit). Nothing else — Python is bundled.

### Why it asks for administrator

Windows blocks a normal program from sending keystrokes to a window owned by
an *elevated* program — a security feature called UIPI. Without admin rights,
KeyMagic would silently do nothing whenever an admin-level app (many IDEs,
system consoles) had focus. Running elevated is what makes "works everywhere"
actually true.

---

## How it works

Three problems have to be solved for a tool like this to feel reliable. Each
one has a specific answer in the code.

### 1. Reading the text without a race condition

The naive approach — send <kbd>Ctrl</kbd>+<kbd>C</kbd>, `sleep(0.1)`, read the
clipboard — is a race by construction. The sleep is a guess, and nothing
guarantees the source app finished writing.

KeyMagic reads Windows' **clipboard sequence number** before sending the copy,
then polls that counter until it actually changes. The OS increments it on
every clipboard write, from any process, so it is a real signal rather than a
guess. Afterwards the original clipboard content is written back, so the tool
never costs you what you had copied.

→ [`core/clipboard_manager.py`](core/clipboard_manager.py)

### 2. Claiming the hotkeys without breaking them

<kbd>F10</kbd> is Windows' standard "activate the menu bar" key. <kbd>Ctrl</kbd>+<kbd>T</kbd>
opens a browser tab. If the app doesn't *consume* those keys, pressing them
moves focus into Word's ribbon before KeyMagic can act.

The first implementation used the `keyboard` library's suppression hook — and
it broke things in a subtle way. To suppress combinations, that hook must
buffer every <kbd>Ctrl</kbd> press to see what follows, which also caught the
synthetic <kbd>Ctrl</kbd>+<kbd>C</kbd> the app sends itself and released the
pieces out of order. The target window received a bare `c` and typed a stray
character into the document. It showed up as `sghl` + <kbd>F10</kbd> producing
`سلامز` — that trailing `ز` being exactly `c` run through the layout map.

The fix was to drop the library and use the OS-native **`RegisterHotKey`** API.
Windows claims the combination itself and posts a message to us; the foreground
app never sees the keystroke, and no hook sits in the path of injected input.
`MOD_NOREPEAT` additionally makes held-key auto-repeat impossible at the source.

→ [`core/hotkey_listener.py`](core/hotkey_listener.py)

### 3. Typing into applications that reject synthetic input

Key events are built by hand and injected through **`SendInput`** with a real
hardware scan code resolved via `MapVirtualKeyW` — the same signal path a
physical keyboard driver produces. Some hardened applications inspect the scan
code and discard events that carry only a virtual-key code.

→ [`core/input_simulator.py`](core/input_simulator.py)

### The layout map

A full bidirectional map between the US QWERTY layout and the standard Iranian
Persian layout — letters, digits, punctuation and shifted symbols. It maps by
**physical key position**, not meaning, which is the whole point: your
keystrokes landed on the right keys, just produced the wrong characters.

Script detection counts characters in the Arabic Unicode block versus Latin and
converts toward whichever is *not* dominant, so one key handles both directions.

→ [`core/layout_map.py`](core/layout_map.py)

---

## Settings

Left-click the tray icon for the control panel.

| Setting | Default | Notes |
|:--|:--|:--|
| Mute notification sound | Off | Toast still appears, just silently |
| Show notifications | On | Hides the toasts entirely |
| Start with Windows | **On** | Per-user registry entry; also removable from Windows Startup Apps |
| Language | English | Switches the whole UI, including RTL layout |

Preferences: `%APPDATA%\KeyMagic\settings.json`
Log: `%LOCALAPPDATA%\KeyMagic\keymagic.log`

<div align="center">
<img src="assets/screenshots/about-en.png" width="330" alt="About page">
</div>

---

## Build from source

```bash
git clone https://github.com/kterfan/KeyMagic.git
cd KeyMagic
pip install -r requirements.txt
python main.py
```

To produce the installers:

```bash
python build.py
```

This freezes the app with PyInstaller, regenerates the installer artwork and
the Persian wizard translation from source, then compiles both packages into
`dist/installer/`. Requires [Inno Setup 6](https://jrsoftware.org/isdl.php) for
the EXE and [WiX Toolset v3](https://wixtoolset.org/) for the MSI; either step
is skipped with a clear message if its toolchain is missing.

### Project layout

```
main.py                   entry point: elevation check, logging
build.py                  freeze → EXE installer → MSI
core/
  config.py               hotkey bindings, timings, retry counts
  settings.py             persisted preferences
  i18n.py                 English/Persian strings + RTL flag
  elevation.py            admin detection + UAC self-relaunch
  startup.py              "start with Windows" registry entry
  hotkey_listener.py      RegisterHotKey + message loop
  input_simulator.py      SendInput hardware-level key injection
  clipboard_manager.py    race-free clipboard I/O
  layout_map.py           EN↔FA key mapping, script detection
  actions.py              the three hotkey actions
  notifier.py             toasts, with mute/hide controls
  icon.py                 procedurally drawn 3D keycap icon
  flyout.py               control panel + About page
  tray.py                 system tray icon
  app.py                  wiring, pause state
installer/
  KeyMagic.iss            bilingual Inno Setup script
  KeyMagic.wxs            WiX source for the MSI
  make_wizard_art.py      generates the wizard banner
  make_persian_isl.py     generates the Persian/RTL language file
```

The icon is drawn at runtime with Pillow — a 3D extruded keycap rendered at 4×
and downscaled, so there are no binary art assets to keep in sync and the
paused state is just a recolor of the same geometry.

---

## FAQ

**Does it send my text anywhere?**
No. Layout conversion is a local lookup table. The only network activity is
opening your browser when you press <kbd>Ctrl</kbd>+<kbd>G</kbd> or
<kbd>Ctrl</kbd>+<kbd>T</kbd>, which sends the selected text to Google exactly as
if you had typed it there yourself.

**Why does F10 convert the whole line?**
When nothing is selected, KeyMagic selects from the caret back to the start of
the line. Select a smaller range first if you want only part of it converted.

**A hotkey doesn't work.**
Another application probably claimed it first — `RegisterHotKey` is exclusive.
Check the log for `Failed to register hotkey`. You can change the bindings in
[`core/config.py`](core/config.py) and rebuild.

**Can I use it without installing?**
Yes — clone the repo and run `python main.py`.

**Does it support other layouts?**
Only English ↔ Persian today. The map in `core/layout_map.py` is a plain
dictionary; adding another layout is mostly data entry. PRs welcome.

---

## Contributing

Issues and pull requests are welcome. If you're reporting a bug, the log at
`%LOCALAPPDATA%\KeyMagic\keymagic.log` is the most useful thing to attach.

## License

[MIT](LICENSE) © Erfan Esmailzadeh

<br>

---

<div dir="rtl" align="right">

<h2 id="-فارسی">🇮🇷 فارسی</h2>

<div align="center">

**اصلاح متن تایپ‌شده با چیدمان اشتباه، در هر برنامه‌ای**

### [⬇️ دانلود برای ویندوز](https://github.com/kterfan/KeyMagic/releases/latest)

</div>

### مشکل چیست؟

شروع می‌کنید به نوشتن یک پیام فارسی، اما کیبورد هنوز روی انگلیسی است:

<div dir="ltr" align="left">

```
سلام چطوری   →   sghl ]xdvd
```

</div>

حالا باید همه‌اش را پاک کنید و از نو بنویسید. هر روز. در هر برنامه‌ای.

**KeyMagic با یک کلید درستش می‌کند.** بدون اینکه چیزی را انتخاب کنید، کلید
<kbd>F10</kbd> را بزنید — متنی که همین الان نوشتید، در همان‌جا و در همان
برنامه‌ای که بودید، با چیدمان درست بازنویسی می‌شود.

<div dir="ltr" align="left">

```
sghl ]xdvd   →   سلام چطوری          [F10]
lk kld n,kl  →   من نمی دونم         [F10]
```

</div>

در هر دو جهت کار می‌کند: چه فارسی که با چیدمان انگلیسی تایپ شده، چه انگلیسی که
با چیدمان فارسی تایپ شده — همان یک کلید، همان نتیجه.

### امکانات

| میان‌بر | کاری که انجام می‌دهد |
|:--|:--|
| <kbd>F10</kbd> | **اصلاح چیدمان** — متن انتخاب‌شده، یا اگر چیزی انتخاب نشده باشد، خط جاری |
| <kbd>Ctrl</kbd>+<kbd>G</kbd> | **جست‌وجوی هوشمند** — متن انتخاب‌شده را در گوگل جست‌وجو می‌کند |
| <kbd>Ctrl</kbd>+<kbd>T</kbd> | **ترجمهٔ سریع** — متن را در گوگل ترنسلیت باز می‌کند |

- **همه‌جا کار می‌کند** — ورد، کروم، تلگرام، VS Code، ترمینال، حتی برنامه‌های با دسترسی ادمین
- **کلیپ‌بوردتان را از بین نمی‌برد** — هر چه کپی کرده بودید، بعد از عملیات برمی‌گردد
- **بی‌صدا و بدون پنجره** — در سینی سیستم اجرا می‌شود؛ صدای اعلان‌ها را هم می‌توانید کامل خاموش کنید
- **رابط کاربری دوزبانه** — انگلیسی و فارسی، با راست‌چینی کامل
- **اجرا با شروع ویندوز** — پیش‌فرض روشن، با یک کلیک خاموش می‌شود، و همیشه قابل خروج است

### نصب

فایل نصب را دانلود و اجرا کنید:

**[⬇️ KeyMagic-Setup.exe](https://github.com/kterfan/KeyMagic/releases/latest)** —
انتخاب معمول. ویزارد دوزبانه است و در همان صفحهٔ اول زبان را می‌پرسد.

**[⬇️ KeyMagic.msi](https://github.com/kterfan/KeyMagic/releases/latest)** —
برای استقرار سازمانی از طریق Group Policy یا Intune.

> **ویندوز ممکن است هشدار دهد** که ناشر ناشناس است. این طبیعی است — فایل نصب
> امضای دیجیتال ندارد، چون گواهی امضای کد سالانه چند صد دلار هزینه دارد. روی
> **More info ← Run anyway** بزنید. می‌توانید خودتان کد را کلون کرده و با
> `python build.py` فایل نصب را بسازید.

**پیش‌نیاز:** ویندوز ۱۰ یا ۱۱ (۶۴ بیتی). چیز دیگری لازم نیست — پایتون داخل فایل قرار دارد.

#### چرا دسترسی ادمین می‌خواهد؟

ویندوز اجازه نمی‌دهد یک برنامهٔ معمولی به پنجرهٔ برنامه‌ای که با دسترسی بالاتر
اجرا شده کلید بفرستد — سازوکاری امنیتی به نام UIPI. بدون دسترسی ادمین،
KeyMagic هر وقت یک برنامهٔ ادمین (مثل خیلی از IDEها) فعال بود بی‌صدا کار نمی‌کرد.
اجرا با دسترسی بالا همان چیزی است که «همه‌جا کار می‌کند» را واقعی می‌کند.

### چطور کار می‌کند؟

برای اینکه چنین ابزاری واقعاً قابل‌اتکا باشد، سه مسئله باید حل شود:

**۱. خواندن متن بدون شرایط رقابتی (race condition)**

روش ساده‌انگارانه — فرستادن <kbd>Ctrl</kbd>+<kbd>C</kbd>، کمی صبر کردن، و بعد
خواندن کلیپ‌بورد — ذاتاً یک شرط رقابتی است: مدت صبر یک حدس است و هیچ تضمینی
نیست که برنامهٔ مبدأ کارش را تمام کرده باشد.

KeyMagic به‌جای حدس زدن، **شمارهٔ ترتیب کلیپ‌بورد** ویندوز را قبل از کپی ثبت
می‌کند و منتظر می‌ماند تا واقعاً تغییر کند. سیستم‌عامل این شمارنده را با هر
تغییر کلیپ‌بورد از هر پروسه‌ای افزایش می‌دهد، پس یک سیگنال واقعی است نه یک
تخمین. در پایان هم محتوای اصلی کلیپ‌بورد بازگردانده می‌شود.

**۲. تصاحب کلیدهای میان‌بر بدون خراب کردنشان**

<kbd>F10</kbd> در ویندوز کلید استاندارد «فعال‌سازی نوار منو» است و
<kbd>Ctrl</kbd>+<kbd>T</kbd> در مرورگر تب جدید باز می‌کند. اگر برنامه این
کلیدها را *مصرف* نکند، فشردنشان قبل از هر کاری فوکوس را به ریبون ورد می‌برد.

پیاده‌سازی اول از هوک کتابخانهٔ `keyboard` استفاده می‌کرد و به شکل ظریفی خراب
بود: آن هوک برای تشخیص ترکیب‌ها مجبور است هر بار فشردن <kbd>Ctrl</kbd> را بافر
کند، و همین <kbd>Ctrl</kbd>+<kbd>C</kbd> ساختگی خود برنامه را هم می‌گرفت و
اجزایش را بی‌ترتیب رها می‌کرد. نتیجه اینکه پنجرهٔ مقصد یک حرف `c` خالی دریافت
می‌کرد. این خودش را به شکل تبدیل `sghl` به `سلامز` نشان داد — آن `ز` اضافه
دقیقاً همان `c` بود که از نگاشت چیدمان رد شده بود.

راه‌حل، کنار گذاشتن کامل آن کتابخانه و استفاده از API بومی
**`RegisterHotKey`** بود. سیستم‌عامل خودش ترکیب کلید را تصاحب می‌کند و پیام را
به ما می‌فرستد؛ برنامهٔ فعال اصلاً کلید را نمی‌بیند و هیچ هوکی سر راه ورودی
تزریق‌شده نیست.

**۳. تایپ در برنامه‌هایی که ورودی مصنوعی را رد می‌کنند**

رویدادهای کلید دستی ساخته و از طریق **`SendInput`** با کد سخت‌افزاری واقعی
تزریق می‌شوند — همان مسیری که یک درایور کیبورد فیزیکی تولید می‌کند. بعضی
برنامه‌های سخت‌گیر این کد را بررسی می‌کنند و رویدادهایی را که فقط کد مجازی
دارند دور می‌ریزند.

**نگاشت چیدمان**

یک نگاشت کامل دوطرفه بین چیدمان QWERTY آمریکایی و چیدمان استاندارد فارسی —
حروف، ارقام، نشانه‌گذاری و نمادهای Shift‌دار. نگاشت بر اساس **موقعیت فیزیکی
کلید** است نه معنای آن، و اصل ماجرا هم همین است: انگشتان شما روی کلیدهای درست
نشستند، فقط کاراکترهای اشتباهی تولید شد.

### تنظیمات

برای باز کردن پنل کنترل، روی آیکون سینی سیستم کلیک کنید.

| تنظیم | پیش‌فرض | توضیح |
|:--|:--|:--|
| بی‌صدا کردن اعلان‌ها | خاموش | اعلان نمایش داده می‌شود، فقط بدون صدا |
| نمایش اعلان‌ها | روشن | با خاموش کردن، اعلان‌ها کامل مخفی می‌شوند |
| اجرا هنگام شروع ویندوز | **روشن** | از داخل برنامه یا تنظیمات ویندوز قابل خاموش کردن |
| زبان | انگلیسی | کل رابط کاربری از جمله راست‌چینی را تغییر می‌دهد |

تنظیمات: `%APPDATA%\KeyMagic\settings.json`
گزارش: `%LOCALAPPDATA%\KeyMagic\keymagic.log`

### ساخت از روی کد

<div dir="ltr" align="left">

```bash
git clone https://github.com/kterfan/KeyMagic.git
cd KeyMagic
pip install -r requirements.txt
python main.py
```

</div>

برای ساخت فایل‌های نصب دستور `python build.py` را اجرا کنید. این دستور برنامه
را با PyInstaller بسته‌بندی می‌کند، تصاویر و ترجمهٔ فارسی ویزارد را از روی کد
بازتولید می‌کند و هر دو بسته را در `dist/installer/` می‌سازد.

### پرسش‌های متداول

**آیا متن من جایی فرستاده می‌شود؟**
خیر. تبدیل چیدمان یک جدول محلی است. تنها ارتباط شبکه‌ای وقتی است که
<kbd>Ctrl</kbd>+<kbd>G</kbd> یا <kbd>Ctrl</kbd>+<kbd>T</kbd> بزنید، که متن را
دقیقاً مثل زمانی که خودتان در گوگل تایپ کنید ارسال می‌کند.

**چرا F10 کل خط را تبدیل می‌کند؟**
وقتی چیزی انتخاب نشده باشد، KeyMagic از مکان‌نما تا ابتدای خط را انتخاب می‌کند.
اگر فقط بخشی را می‌خواهید، اول همان بخش را انتخاب کنید.

**یکی از میان‌برها کار نمی‌کند.**
احتمالاً برنامهٔ دیگری زودتر آن را گرفته است — `RegisterHotKey` انحصاری است.
در فایل گزارش دنبال `Failed to register hotkey` بگردید.

**آیا چیدمان‌های دیگر پشتیبانی می‌شوند؟**
فعلاً فقط انگلیسی ↔ فارسی. نگاشت در `core/layout_map.py` یک دیکشنری ساده است و
اضافه کردن چیدمان جدید عمدتاً وارد کردن داده است. Pull Request پذیرفته می‌شود.

### مجوز

[MIT](LICENSE) © عرفان اسماعیل‌زاده

</div>

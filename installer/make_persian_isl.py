"""
Generates `installer/Persian.isl` — the Farsi language file for the wizard.

Inno Setup does not ship a Persian translation, and a language file must be
*complete*: any message the compiler cannot find is a build error. So rather
than writing 400+ strings by hand, this starts from the bundled English
`Default.isl` and overwrites the messages a user actually sees during a
normal install, plus the `[LangOptions]` block that switches the wizard to
right-to-left and picks a Persian-capable font.

Messages left untranslated are the rare diagnostic/error strings (disk full,
corrupted installer, and so on). They stay English, but still render in the
RTL layout. That tradeoff is deliberate: a partial translation of the paths
users actually walk beats a machine-mangled full one.
"""

from __future__ import annotations

import os
import re

INNO_DIR = r"C:\Program Files (x86)\Inno Setup 6"
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Persian.isl")

# Farsi is $0429. Codepage 0 = Unicode, correct for Inno Setup 6 (Unicode-only).
# Tahoma is the most reliable Persian face that ships with every Windows.
_LANG_OPTIONS = """[LangOptions]
LanguageName=<0641><0627><0631><0633><06CC>
LanguageID=$0429
LanguageCodePage=0
RightToLeft=yes
DialogFontName=Tahoma
DialogFontSize=9
WelcomeFontName=Tahoma
WelcomeFontSize=12
"""
# Note: TitleFont*/CopyrightFont* are accepted by older Inno versions but are
# obsolete in 6.x (the modern wizard style draws those itself) and emit
# compiler warnings, so they are deliberately omitted.

# key -> Persian text. Only messages on the normal install path.
_TRANSLATIONS = {
    # Buttons and common UI
    "ButtonBack": "« &قبلی",
    "ButtonNext": "&بعدی »",
    "ButtonInstall": "&نصب",
    "ButtonOK": "تأیید",
    "ButtonCancel": "انصراف",
    "ButtonYes": "&بله",
    "ButtonNo": "&خیر",
    "ButtonFinish": "&پایان",
    "ButtonBrowse": "&انتخاب مسیر...",
    "ButtonWizardBrowse": "&انتخاب مسیر...",
    "ButtonNewFolder": "&ساخت پوشهٔ جدید",
    "ExitSetupTitle": "خروج از نصب",
    # Inno's line-break escape is %n, not \n. Writing \n here puts a literal
    # backslash-n on screen — it showed up verbatim on the welcome page.
    "ExitSetupMessage": "نصب کامل نشده است. اگر اکنون خارج شوید، برنامه نصب نخواهد شد."
                        "%n%nآیا می‌خواهید از نصب خارج شوید؟",
    "AboutSetupNote": "",
    "TranslatorNote": "",
    # Language picker
    "SelectLanguageTitle": "انتخاب زبان نصب",
    "SelectLanguageLabel": "زبان مورد نظر برای نصب را انتخاب کنید:",
    # Welcome page
    "WelcomeLabel1": "به نصب‌کنندهٔ [name] خوش آمدید",
    "WelcomeLabel2": "این برنامه [name/ver] را روی رایانهٔ شما نصب می‌کند."
                     "%n%nساخته‌شده توسط عرفان اسماعیل‌زاده"
                     "%n%nپیش از ادامه، بستن سایر برنامه‌ها توصیه می‌شود.",
    "ClickNext": "برای ادامه «بعدی» و برای خروج «انصراف» را بزنید.",
    # Destination page
    "WizardSelectDir": "انتخاب محل نصب",
    "SelectDirDesc": "[name] در کجا نصب شود؟",
    "SelectDirLabel3": "برنامه در پوشهٔ زیر نصب خواهد شد.",
    "SelectDirBrowseLabel": "برای ادامه «بعدی» را بزنید. برای انتخاب پوشه‌ای دیگر «انتخاب مسیر» را بزنید.",
    "DiskSpaceGBLabel": "دست‌کم [gb] گیگابایت فضای خالی دیسک لازم است.",
    "DiskSpaceMBLabel": "دست‌کم [mb] مگابایت فضای خالی دیسک لازم است.",
    "InvalidPath": "باید یک مسیر کامل به همراه نام درایو وارد کنید.",
    "DirNameTooLong": "نام یا مسیر پوشه بیش از حد طولانی است.",
    "InvalidDirName": "نام پوشه معتبر نیست.",
    "BadDirName32": "نام پوشه نمی‌تواند شامل این نویسه‌ها باشد:%n%n%1",
    "DirExistsTitle": "پوشه از پیش وجود دارد",
    "DirExists": "پوشهٔ:%n%n%1%n%nاز پیش وجود دارد. آیا مایل به نصب در آن هستید؟",
    "DirDoesntExistTitle": "پوشه وجود ندارد",
    "DirDoesntExist": "پوشهٔ:%n%n%1%n%nوجود ندارد. آیا ساخته شود؟",
    # Start menu page
    "WizardSelectProgramGroup": "انتخاب پوشهٔ منوی شروع",
    "SelectStartMenuFolderDesc": "میان‌برهای برنامه کجا قرار گیرند؟",
    "SelectStartMenuFolderLabel3": "میان‌برها در پوشهٔ زیر ساخته می‌شوند.",
    "SelectStartMenuFolderBrowseLabel": "برای ادامه «بعدی» را بزنید. برای انتخاب پوشه‌ای دیگر «انتخاب مسیر» را بزنید.",
    "NoIconsCheck": "میان‌بری ساخته &نشود",
    # Tasks page
    "WizardSelectTasks": "انتخاب کارهای اضافی",
    "SelectTasksDesc": "چه کارهای دیگری انجام شود؟",
    "SelectTasksLabel2": "کارهای اضافی مورد نظر را انتخاب و سپس «بعدی» را بزنید.",
    # Ready page
    "WizardReady": "آمادهٔ نصب",
    "ReadyLabel1": "برنامه آمادهٔ نصب [name] روی رایانهٔ شماست.",
    "ReadyLabel2a": "برای ادامه «نصب» و برای بازبینی تنظیمات «قبلی» را بزنید.",
    "ReadyLabel2b": "برای ادامهٔ نصب «نصب» را بزنید.",
    "ReadyMemoUserInfo": "اطلاعات کاربر:",
    "ReadyMemoDir": "محل نصب:",
    "ReadyMemoType": "نوع نصب:",
    "ReadyMemoComponents": "اجزای انتخاب‌شده:",
    "ReadyMemoGroup": "پوشهٔ منوی شروع:",
    "ReadyMemoTasks": "کارهای اضافی:",
    # Installing page
    "WizardInstalling": "در حال نصب",
    "InstallingLabel": "لطفاً تا پایان نصب [name] روی رایانه‌تان صبر کنید.",
    "StatusExtractFiles": "در حال استخراج فایل‌ها...",
    "StatusCreateIcons": "در حال ساخت میان‌برها...",
    "StatusCreateDirs": "در حال ساخت پوشه‌ها...",
    "StatusRunProgram": "در حال تکمیل نصب...",
    "StatusRollback": "در حال بازگرداندن تغییرات...",
    # Finished page
    "FinishedHeadingLabel": "نصب [name] به پایان رسید",
    "FinishedLabel": "[name] روی رایانهٔ شما نصب شد. برای اجرا، روی میان‌بر ساخته‌شده کلیک کنید.",
    "FinishedLabelNoIcons": "[name] روی رایانهٔ شما نصب شد.",
    "ClickFinish": "برای خروج از نصب «پایان» را بزنید.",
    "RunEntryExec": "اجرای %1",
    # Uninstall
    "UninstallAppTitle": "حذف برنامه",
    "UninstallAppFullTitle": "حذف %1",
    "ConfirmUninstall": "آیا مطمئنید که می‌خواهید %1 و همهٔ اجزای آن حذف شود؟",
    "UninstallStatusLabel": "لطفاً تا حذف کامل %1 از رایانه‌تان صبر کنید.",
    "UninstalledAll": "%1 با موفقیت از رایانهٔ شما حذف شد.",
    "UninstalledMost": "حذف %1 به پایان رسید.%n%nبرخی موارد قابل حذف نبودند و می‌توانید آن‌ها را دستی پاک کنید.",
}


def main() -> None:
    with open(os.path.join(INNO_DIR, "Default.isl"), "r", encoding="utf-8-sig") as handle:
        content = handle.read()

    # Swap the whole [LangOptions] block for the Persian/RTL one.
    content = re.sub(
        r"\[LangOptions\].*?(?=\n\[)", _LANG_OPTIONS, content, count=1, flags=re.S
    )

    replaced, missing = 0, []
    for key, value in _TRANSLATIONS.items():
        pattern = re.compile(rf"^{re.escape(key)}=.*$", flags=re.M)
        if pattern.search(content):
            content = pattern.sub(lambda _m, v=value: f"{key}={v}", content, count=1)
            replaced += 1
        else:
            missing.append(key)

    # Inno Setup 6 reads .isl as UTF-8; the BOM makes the encoding explicit.
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="\r\n") as handle:
        handle.write(content)

    print(f"Persian.isl written: {replaced} messages translated.")
    if missing:
        print(f"  (skipped {len(missing)} keys not present in this Inno version: {', '.join(missing)})")


if __name__ == "__main__":
    main()

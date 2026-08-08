"""
One-command build: source -> frozen app -> installers.

    python build.py            # everything that's available
    python build.py --exe-only # skip the MSI step

Steps
------
1. PyInstaller freezes the app into `dist/KeyMagic/`.
2. Wizard artwork and the Persian language file are regenerated, so the
   installer can never ship art or translations that lag the source.
3. Inno Setup compiles the bilingual EXE installer.
4. WiX (if installed) compiles the MSI.

Every step reports clearly whether it ran or was skipped — a build that
silently produces fewer artifacts than expected is worse than one that
tells you why.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
INSTALLER_DIR = os.path.join(ROOT, "installer")

APP_NAME = "KeyMagic"
VERSION = "1.0.4"

ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]
WIX_CANDIDATES = [
    r"C:\Program Files (x86)\WiX Toolset v3.14\bin",
    r"C:\Program Files (x86)\WiX Toolset v3.11\bin",
    os.path.expanduser(r"~\.dotnet\tools"),
]


def run(command: list[str], cwd: str | None = None) -> None:
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def find_first(paths: list[str], filename: str) -> str | None:
    for directory in paths:
        candidate = os.path.join(directory, filename) if os.path.isdir(directory) else directory
        if os.path.isfile(candidate):
            return candidate
    return None


def step_freeze() -> None:
    print("\n=== [1/4] Freezing app with PyInstaller ===")
    build_dir = os.path.join(DIST, APP_NAME)
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)

    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",                 # no console window
        "--name", APP_NAME,
        "--icon", os.path.join(ROOT, "assets", "icon.ico"),
        # --uac-admin embeds the manifest so Windows elevates at launch,
        # which is required to send input to elevated windows (UIPI).
        "--uac-admin",
        "--add-data", f"{os.path.join(ROOT, 'assets')}{os.pathsep}assets",
        os.path.join(ROOT, "main.py"),
    ], cwd=ROOT)


def step_assets() -> None:
    print("\n=== [2/4] Generating wizard art + Persian language file ===")
    run([sys.executable, os.path.join(INSTALLER_DIR, "make_wizard_art.py")], cwd=ROOT)
    run([sys.executable, os.path.join(INSTALLER_DIR, "make_persian_isl.py")], cwd=ROOT)


def step_inno() -> bool:
    print("\n=== [3/4] Building EXE installer (Inno Setup) ===")
    iscc = find_first(ISCC_CANDIDATES, "ISCC.exe")
    if iscc is None:
        print("  SKIPPED — Inno Setup 6 not found.")
        print("  Install: winget install JRSoftware.InnoSetup")
        return False
    run([iscc, os.path.join(INSTALLER_DIR, "KeyMagic.iss")], cwd=INSTALLER_DIR)
    return True


def step_msi() -> bool:
    print("\n=== [4/4] Building MSI (WiX) ===")
    out_dir = os.path.join(DIST, "installer")
    os.makedirs(out_dir, exist_ok=True)

    wix = find_first(WIX_CANDIDATES, "wix.exe")
    if wix is not None:  # WiX v4+ single-CLI
        run([
            wix, "build",
            os.path.join(INSTALLER_DIR, "KeyMagic.wxs"),
            "-arch", "x64",
            "-d", f"AppVersion={VERSION}",
            "-d", f"SourceDir={os.path.join(DIST, APP_NAME)}",
            "-o", os.path.join(out_dir, f"{APP_NAME}-{VERSION}.msi"),
        ], cwd=INSTALLER_DIR)
        return True

    candle = find_first(WIX_CANDIDATES, "candle.exe")
    light = find_first(WIX_CANDIDATES, "light.exe")
    if candle and light:  # WiX v3 two-step
        obj = os.path.join(out_dir, "KeyMagic.wixobj")
        run([candle, "-arch", "x64", f"-dAppVersion={VERSION}",
             f"-dSourceDir={os.path.join(DIST, APP_NAME)}",
             "-o", obj, os.path.join(INSTALLER_DIR, "KeyMagic.wxs")], cwd=INSTALLER_DIR)
        run([light, "-ext", "WixUIExtension", "-o",
             os.path.join(out_dir, f"{APP_NAME}-{VERSION}.msi"), obj], cwd=INSTALLER_DIR)
        return True

    print("  SKIPPED — WiX Toolset not found.")
    print("  Install either:")
    print("    winget install WiXToolset.WiXToolset      (v3, needs .NET 3.5 feature)")
    print("    dotnet tool install --global wix          (v4+, needs .NET SDK)")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} installers.")
    parser.add_argument("--exe-only", action="store_true", help="skip the MSI step")
    parser.add_argument("--skip-freeze", action="store_true", help="reuse an existing dist/ build")
    args = parser.parse_args()

    if not args.skip_freeze:
        step_freeze()
    step_assets()

    built_exe = step_inno()
    built_msi = False if args.exe_only else step_msi()

    print("\n" + "=" * 60)
    print("Build summary")
    print("=" * 60)
    print(f"  Frozen app : dist/{APP_NAME}/{APP_NAME}.exe")
    print(f"  EXE setup  : {'dist/installer/%s-%s-Setup.exe' % (APP_NAME, VERSION) if built_exe else 'NOT BUILT'}")
    print(f"  MSI        : {'dist/installer/%s-%s.msi' % (APP_NAME, VERSION) if built_msi else 'NOT BUILT'}")


if __name__ == "__main__":
    main()

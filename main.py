"""
KeyMagic — entry point.

Run with:  python main.py
Or build a windowless executable with:
    pyinstaller --onefile --noconsole --name KeyMagic main.py
"""

from __future__ import annotations

import logging
import os
import sys

from core.app import KeyMagicApp
from core.config import UI
from core.elevation import ensure_admin


def _configure_logging() -> None:
    log_dir = os.path.join(os.environ.get("LOCALAPPDATA", "."), UI.APP_NAME)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, UI.LOG_FILENAME)

    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    # Only attach a console handler if we actually have a console (i.e. not
    # a --noconsole PyInstaller build, where sys.stdout may be None).
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> None:
    # Must happen before anything else: if we're not elevated yet, this
    # relaunches the process with a UAC prompt and exits the current one,
    # so there is no point doing any other setup first.
    ensure_admin()

    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting %s (elevated)...", UI.APP_NAME)

    app = KeyMagicApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()


if __name__ == "__main__":
    main()

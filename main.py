#!/usr/bin/env python3
"""
Linux Mouse Fix — Entry Point
A Mac Mouse Fix-inspired mouse gesture tool for Ubuntu.

Usage:
    python3 main.py          # GUI mode (UI only, engine needs root)
    sudo python3 main.py     # Full mode (engine + UI with root)
"""

import sys
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("LinuxMouseFix")


def main():
    # Check if running as root (needed for evdev grab)
    is_root = os.geteuid() == 0
    if not is_root:
        log.warning(
            "Root yetkisi yok — Motor devre dışı. "
            "Tam çalışma için: sudo python3 main.py"
        )

    # Import and run the GTK app
    from ui_app import main as run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())

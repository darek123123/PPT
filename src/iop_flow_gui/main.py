from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from .app import MainWindow


def main(argv: Optional[list[str]] = None) -> int:
    # Offscreen smoke: create and exit
    platform = os.environ.get("QT_QPA_PLATFORM", "")
    app = QApplication(argv or sys.argv)
    win = MainWindow()
    if platform == "offscreen":
        # create widgets without entering event loop
        win.show()  # harmless in offscreen
        win.close()
        return 0
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

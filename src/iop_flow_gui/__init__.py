from __future__ import annotations

"""iop_flow_gui package

This package configures a safe Qt platform for headless environments (e.g., CI)
by setting QT_QPA_PLATFORM=offscreen when no DISPLAY is present on non-Windows
systems. This avoids ImportError related to missing libEGL/libxcb backends
when importing PySide6 in test environments.
"""

import os

# On Linux/macOS in headless CI (no DISPLAY), force Qt to use the offscreen
# platform plugin to avoid linking against GUI backends like xcb/eglfs.
if os.name != "nt":
    platform = os.environ.get("QT_QPA_PLATFORM", "")
    if not platform and os.environ.get("DISPLAY", "") == "":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
__all__ = []

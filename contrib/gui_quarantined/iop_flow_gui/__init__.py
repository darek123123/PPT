"""
Initialize iop_flow_gui package and ensure Qt offscreen mode when needed.
"""

from __future__ import annotations
import os

# On Linux/macOS in headless CI (no DISPLAY), force Qt to use the offscreen
# platform plugin to allow Matplotlib/Qt to render without a window server.
if os.name != "nt" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# On Linux/macOS in headless CI (no DISPLAY), force Qt to use the offscreen
# platform plugin to avoid linking against GUI backends like xcb/eglfs.
if os.name != "nt":
    platform = os.environ.get("QT_QPA_PLATFORM", "")
    if not platform and os.environ.get("DISPLAY", "") == "":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
__all__ = []

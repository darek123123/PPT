from __future__ import annotations

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
try:
    from shiboken6 import isValid as _qt_is_valid  # PySide6 runtime check
except Exception:  # pragma: no cover
    def _qt_is_valid(obj) -> bool:  # type: ignore[no-redef]
        try:
            return bool(obj)
        except Exception:
            return False


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self) -> None:
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

    def clear(self) -> None:
        try:
            if not _qt_is_valid(self):
                return
            self.ax.clear()
        except RuntimeError:
            pass

    def plot_xy(self, x, y, label: str | None = None) -> None:
        try:
            if not _qt_is_valid(self):
                return
            self.ax.plot(x, y, label=label)
            if label:
                self.ax.legend()
        except RuntimeError:
            pass

    def render(self) -> None:
        try:
            if not _qt_is_valid(self):
                return
            # Use immediate draw to avoid queued _draw_idle after deletion
            self.draw()
        except RuntimeError:
            # Happens if Qt widget already deleted; ignore
            pass

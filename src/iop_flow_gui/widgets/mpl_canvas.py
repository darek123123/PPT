from __future__ import annotations

from typing import Tuple

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
try:
    from shiboken6 import isValid as _qt_is_valid  # PySide6 runtime check
except Exception:  # pragma: no cover
    def _qt_is_valid(obj) -> bool:  # type: ignore[no-redef]
        try:
            return bool(obj)
        except Exception:
            return False


class MplCanvas(QWidget):
    """
    Qt widget composing a Matplotlib FigureCanvas with a small readout QLabel.
    Provides a simple API: clear(), plot_xy(...), render(), set_readout_units(xu, yu).
    """

    def __init__(self) -> None:
        super().__init__()
        # Figure/canvas setup
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self.fig)
        # Readout (x,y)
        self.readout = QLabel("", self)
        self.readout.setStyleSheet("color: #555; font-size: 11px;")
        self._units: Tuple[str, str] = ("", "")  # (x_unit, y_unit)
        # Test hook: store last plotted point count (len(x) from last plot_xy call)
        self.last_points_count = 0
        # Layout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)
        lay.addWidget(self.readout)
        # Cursor and motion events
        try:
            self._cursor = Cursor(self.ax, useblit=True, color='gray', linewidth=0.8)
        except Exception:
            self._cursor = None  # pragma: no cover
        try:
            self._cid_motion = self._canvas.mpl_connect('motion_notify_event', self._on_motion)
        except Exception:
            self._cid_motion = None  # pragma: no cover

    def clear(self) -> None:
        try:
            if not _qt_is_valid(self):
                return
            self.ax.clear()
        except RuntimeError:
            pass

    def plot_xy(
        self,
        x,
        y,
        label: str = "",
        xlabel: str = "",
        ylabel: str = "",
        title: str = "",
        grid: bool = True,
    ) -> None:
        """
        Clear axis, plot a single line, set labels/title, and optionally show grid.
        Preserve legend if label provided.
        """
        try:
            if not _qt_is_valid(self):
                return
            # reset axis
            self.ax.clear()
            # record point count for tests (gracefully handle sequences without __len__)
            try:
                self.last_points_count = len(x)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover - defensive
                self.last_points_count = 0
            # plot
            self.ax.plot(x, y, label=(label or None))
            # labels and aesthetics
            if xlabel:
                self.ax.set_xlabel(xlabel)
            if ylabel:
                self.ax.set_ylabel(ylabel)
            if title:
                self.ax.set_title(title)
            if grid:
                self.ax.grid(True)
            if label:
                self.ax.legend()
        except RuntimeError:
            pass

    def render(self) -> None:
        try:
            if not _qt_is_valid(self):
                return
            # Use immediate draw to avoid queued _draw_idle after deletion
            self._canvas.draw()
        except RuntimeError:
            # Happens if Qt widget already deleted; ignore
            pass

    def set_readout_units(self, xu: str, yu: str) -> None:
        self._units = (xu or "", yu or "")

    # Internal: update readout on mouse move
    def _on_motion(self, event) -> None:
        try:
            if event.inaxes != self.ax:
                self.readout.setText("")
                return
            x = event.xdata
            y = event.ydata
            if x is None or y is None:
                self.readout.setText("")
                return
            xu, yu = self._units
            x_txt = f"x={x:.3f}{(' ' + xu) if xu else ''}"
            y_txt = f"y={y:.3f}{(' ' + yu) if yu else ''}"
            self.readout.setText(f"{x_txt}, {y_txt}")
        except Exception:
            # tolerate any backend/runtime issues
            pass

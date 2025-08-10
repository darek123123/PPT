from __future__ import annotations

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self) -> None:
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

    def clear(self) -> None:
        self.ax.clear()

    def plot_xy(self, x, y, label: str | None = None) -> None:
        self.ax.plot(x, y, label=label)
        if label:
            self.ax.legend()

    def render(self) -> None:
        self.draw_idle()

from __future__ import annotations

def test_mplcanvas_plot_xy_smoke(monkeypatch):
    # Headless setup: Matplotlib non-interactive and Qt offscreen
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import matplotlib
    matplotlib.use("Agg", force=True)
    from PySide6.QtWidgets import QApplication
    _ = QApplication.instance() or QApplication([])

    from iop_flow_gui.widgets.mpl_canvas import MplCanvas

    c = MplCanvas()
    c.set_readout_units("mm", "-")
    x = [0, 1, 2, 3]
    y = [0.0, 0.5, 1.0, 0.5]
    c.plot_xy(x, y, label="test", xlabel="X", ylabel="Y", title="T")
    c.render()

    # If no exception, consider pass; additionally check figure has axes
    assert hasattr(c, "fig") and len(c.fig.axes) >= 1

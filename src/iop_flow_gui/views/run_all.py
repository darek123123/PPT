from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QTableView,
    QHeaderView,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Signal

from iop_flow.io_json import read_session, write_session
from iop_flow.api import run_all as run_all_api
from ..preferences import load_prefs

from ..widgets.mpl_canvas import MplCanvas


COLS = [
    "lift_m",
    "q_m3s_ref",
    "A_ref_key",
    "Cd_ref",
    "V_ref",
    "Mach_ref",
    "SR",
]


class RunAllView(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._session = None
        self._result: Dict[str, Any] | None = None

        lay = QVBoxLayout(self)

        # buttons
        top_row = QHBoxLayout()
        self.btn_back = QPushButton("\u2190 Wróć", self)
        top_row.addWidget(self.btn_back)
        top_row.addStretch(1)
        lay.addLayout(top_row)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("Wczytaj Session JSON…", self)
        self.btn_run = QPushButton("Uruchom", self)
        self.btn_save = QPushButton("Zapisz wyniki JSON…", self)
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_save)
        lay.addLayout(btn_row)

        # tables
        self.tbl_int = QTableView(self)
        self.tbl_exh = QTableView(self)
        for tbl in (self.tbl_int, self.tbl_exh):
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.setEditTriggers(QTableView.NoEditTriggers)
        lay.addWidget(self.tbl_int)
        lay.addWidget(self.tbl_exh)

        # plots
        plot_row = QHBoxLayout()
        self.plot_cd = MplCanvas()
        self.plot_q = MplCanvas()
        plot_row.addWidget(self.plot_cd)
        plot_row.addWidget(self.plot_q)
        lay.addLayout(plot_row)

        # wiring
        self.btn_back.clicked.connect(lambda: self.back_requested.emit())
        self.btn_load.clicked.connect(self._on_load)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_save.clicked.connect(self._on_save)

        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        has_session = self._session is not None
        self.btn_run.setEnabled(has_session)
        self.btn_save.setEnabled(self._result is not None)

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Wczytaj Session JSON", "", "JSON (*.json)")
        if not path:
            return
        self._session = read_session(path)
        self._result = None
        self._refresh_buttons()

    def _on_run(self) -> None:
        if self._session is None:
            return
        prefs = load_prefs()
        import time

        t0 = time.perf_counter()
        self._result = run_all_api(
            self._session,
            dp_ref_inH2O=prefs.dp_ref_inH2O,
            a_ref_mode=prefs.a_ref_mode,
            eff_mode=prefs.eff_mode,
            engine_v_target=prefs.v_target,
        )
        self._populate_tables()
        self._populate_plots()
        self._refresh_buttons()
        try:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage(f"OK ({dt_ms} ms)", 2000)
        except Exception:
            pass

    def _on_save(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz wyniki JSON", "", "JSON (*.json)")
        if not path:
            return
        write_session(path, self._session)  # save original session as well if desired
        # write results
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._result, f, ensure_ascii=False, indent=2)
        try:
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage("OK", 2000)
        except Exception:
            pass

    def _populate_tables(self) -> None:
        assert self._result is not None
        series = self._result["series"]
        self._fill_table(self.tbl_int, series.get("intake", []))
        self._fill_table(self.tbl_exh, series.get("exhaust", []))

    def _fill_table(self, tbl: QTableView, rows: List[Dict[str, Any]]) -> None:
        model = QStandardItemModel(len(rows), len(COLS), self)
        model.setHorizontalHeaderLabels(COLS)
        for r, row in enumerate(rows):
            for c, key in enumerate(COLS):
                val = row.get(key, "")
                text = f"{val:.6g}" if isinstance(val, (int, float)) else str(val)
                model.setItem(r, c, QStandardItem(text))
        tbl.setModel(model)

    def _populate_plots(self) -> None:
        assert self._result is not None
        series = self._result["series"]
        for canvas in (self.plot_cd, self.plot_q):
            canvas.clear()
        ints = series.get("intake", [])
        x = [row["lift_m"] for row in ints]
        y_cd = [row.get("Cd_ref", 0.0) for row in ints]
        y_q = [row.get("q_m3s_ref", 0.0) for row in ints]
        self.plot_cd.plot_xy(x, y_cd, label="Cd_ref")
        self.plot_q.plot_xy(x, y_q, label="q_m3s_ref")
        self.plot_cd.render()
        self.plot_q.render()

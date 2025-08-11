from __future__ import annotations

from typing import Any, Dict, List, Sequence

from PySide6.QtCore import QSettings, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QTableView,
    QHeaderView,
    QMessageBox,
    QLabel,
)

from iop_flow.io_json import read_session
from iop_flow.api import run_compare as run_compare_api
from iop_flow import formulas as F

from ..widgets.mpl_canvas import MplCanvas
from ..wizard.state import lift_m_to_mm, q_m3s_to_cfm


DEFAULT_KEYS: Sequence[str] = ("q_m3s_ref", "Cd_ref", "V_ref", "Mach_ref")


class CompareView(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        self._before_path: str | None = None
        self._after_path: str | None = None
        self._result: Dict[str, Any] | None = None

        self.settings = QSettings("iop_flow_gui", "compare_view")

        root = QVBoxLayout(self)

        # Top/back row
        top_row = QHBoxLayout()
        self.btn_back = QPushButton("\u2190 Wróć", self)
        top_row.addWidget(self.btn_back)
        top_row.addStretch(1)
        root.addLayout(top_row)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_before = QPushButton("Wczytaj Before…", self)
        self.btn_after = QPushButton("Wczytaj After…", self)
        self.btn_run = QPushButton("Porównaj", self)
        self.btn_save = QPushButton("Zapisz różnice JSON…", self)
        btn_row.addWidget(self.btn_before)
        btn_row.addWidget(self.btn_after)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

        # Table
        self.table = QTableView(self)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        root.addWidget(self.table)

        # Plots (Cd and Q* overlays)
        plots = QHBoxLayout()
        self.plot_cd = MplCanvas()
        self.plot_q = MplCanvas()
        plots.addWidget(self.plot_cd)
        plots.addWidget(self.plot_q)
        root.addLayout(plots)

        # Status below plots
        self.lbl_status = QLabel("dp_ref=—, ρ_ref=—, A_ref=—", self)
        root.addWidget(self.lbl_status)

        # Wire up
        self.btn_back.clicked.connect(lambda: self.back_requested.emit())
        self.btn_before.clicked.connect(lambda: self._pick_file("before"))
        self.btn_after.clicked.connect(lambda: self._pick_file("after"))
        self.btn_run.clicked.connect(self._on_run)
        self.btn_save.clicked.connect(self._on_save)

        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        ready = bool(self._before_path and self._after_path)
        self.btn_run.setEnabled(ready)
        self.btn_save.setEnabled(self._result is not None)

    def _last_dir(self) -> str:
        return str(self.settings.value("last_dir", ""))

    def _set_last_dir(self, path: str) -> None:
        import os

        d = path if os.path.isdir(path) else os.path.dirname(path)
        if d:
            self.settings.setValue("last_dir", d)

    def _pick_file(self, which: str) -> None:
        start_dir = self._last_dir()
        title = (
            "Wczytaj Session JSON (Before)" if which == "before" else "Wczytaj Session JSON (After)"
        )
        path, _ = QFileDialog.getOpenFileName(self, title, start_dir, "JSON (*.json)")
        if not path:
            return
        # Try a light validation by attempting to read the session
        try:
            _ = read_session(path)
        except Exception:
            QMessageBox.warning(
                self,
                "Zły format pliku",
                "Wybrany plik nie jest Session JSON. Użyj pliku zapisanego z Kreatora (Zapisz Session JSON…).",
            )
            try:
                win = self.window()
                if hasattr(win, "statusBar"):
                    win.statusBar().showMessage("Błąd: to nie jest Session JSON", 3000)
            except Exception:
                pass
            return
        if which == "before":
            self._before_path = path
        else:
            self._after_path = path
        self._set_last_dir(path)
        self._result = None
        self._refresh_buttons()
        try:
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage("Plik wczytany", 2000)
        except Exception:
            pass

    def _on_run(self) -> None:
        if not (self._before_path and self._after_path):
            return
        try:
            before = read_session(self._before_path)
            after = read_session(self._after_path)
        except Exception:
            QMessageBox.warning(self, "Błąd", "Nie udało się wczytać Session JSON.")
            return
        self._result = run_compare_api(before, after, keys=DEFAULT_KEYS)
        self._populate_table()
        self._populate_plots(before, after)
        self._refresh_buttons()
        try:
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage("OK", 2000)
        except Exception:
            pass

    def _on_save(self) -> None:
        if not self._result:
            return
        start_dir = self._last_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz różnice JSON", start_dir, "JSON (*.json)"
        )
        if not path:
            return
        self._set_last_dir(path)
        to_save = {
            "intake": self._result.get("intake", {}).get("diffs", {}),
            "exhaust": self._result.get("exhaust", {}).get("diffs", {}),
            "params": self._result.get("params", {}),
        }
        import json

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Błąd zapisu", f"Nie udało się zapisać pliku: {e}")
            return
        else:
            QMessageBox.information(self, "Zapisano", "Różnice zapisane poprawnie.")

    def _populate_table(self) -> None:
        assert self._result is not None
        diffs: Dict[str, List[Dict[str, float]]] = self._result.get("intake", {}).get("diffs", {})
        # Columns: lift_m, and for each key: before, after, delta_pct
        cols: List[str] = ["lift_m"]
        for k in DEFAULT_KEYS:
            cols.extend([f"{k}:before", f"{k}:after", f"{k}:delta_pct"])

        # Build row map by lift
        lifts_sorted: List[float] = []
        by_lift: Dict[float, Dict[str, float]] = {}
        for k in DEFAULT_KEYS:
            for item in diffs.get(k, []):
                lm = float(item.get("lift_m", 0.0))
                if lm not in by_lift:
                    by_lift[lm] = {"lift_m": lm}
                    lifts_sorted.append(lm)
                by_lift[lm][f"{k}:before"] = float(item.get("before", 0.0))
                by_lift[lm][f"{k}:after"] = float(item.get("after", 0.0))
                by_lift[lm][f"{k}:delta_pct"] = float(item.get("delta_pct", 0.0))

        lifts_sorted.sort()
        model = QStandardItemModel(len(lifts_sorted), len(cols), self)
        model.setHorizontalHeaderLabels(cols)
        for r, lm in enumerate(lifts_sorted):
            row = by_lift[lm]
            for c, key in enumerate(cols):
                val = row.get(key, "")
                text = f"{val:.6g}" if isinstance(val, (int, float)) else str(val)
                model.setItem(r, c, QStandardItem(text))
        self.table.setModel(model)

    def _populate_plots(self, before_session: Any, after_session: Any) -> None:
        assert self._result is not None
        # Clear plots
        self.plot_cd.clear()
        self.plot_q.clear()

        intake = self._result.get("intake", {})
        before_series = intake.get("before", [])
        after_series = intake.get("after", [])

        # Params for titles/status
        params = self._result.get("params", {})
        a_key = params.get("A_ref_key", "eff")
        try:
            dp_ref = float(params.get("dp_ref_inH2O", 28.0))
        except Exception:
            dp_ref = 28.0
        rho_ref = None
        try:
            air = getattr(after_session, "air", None) or getattr(before_session, "air", None)
            if air:
                rho_ref = F.air_density(F.AirState(air.p_tot, air.T, air.RH))
        except Exception:
            rho_ref = None

        # Cd overlay (Before/After)
        xb_m = [float(r.get("lift_m", 0.0)) for r in before_series]
        yb_cd = [float(r.get("Cd_ref", 0.0)) for r in before_series]
        xa_m = [float(r.get("lift_m", 0.0)) for r in after_series]
        ya_cd = [float(r.get("Cd_ref", 0.0)) for r in after_series]
        xb = lift_m_to_mm(xb_m)
        xa = lift_m_to_mm(xa_m)
        title_cd = f"Cd — Before/After @ {a_key} ΔP={dp_ref:.0f}\" H₂O"
        self.plot_cd.set_readout_units("mm", "-")
        self.plot_cd.plot_xy(xb, yb_cd, label="Before", xlabel="Lift [mm]", ylabel="Cd (-)", title=title_cd)
        self.plot_cd.plot_xy(xa, ya_cd, label="After")
        self.plot_cd.render()

        # Q* overlay (CFM)
        yb_q_cfm = q_m3s_to_cfm([float(r.get("q_m3s_ref", 0.0)) for r in before_series])
        ya_q_cfm = q_m3s_to_cfm([float(r.get("q_m3s_ref", 0.0)) for r in after_series])
        title_q = f"Q* — Before/After @ {a_key} ΔP={dp_ref:.0f}\" H₂O"
        self.plot_q.set_readout_units("mm", "CFM")
        self.plot_q.plot_xy(xb, yb_q_cfm, label="Before", xlabel="Lift [mm]", ylabel="Q* [CFM]", title=title_q)
        self.plot_q.plot_xy(xa, ya_q_cfm, label="After")
        self.plot_q.render()

        # Status
        rho_txt = f"{rho_ref:.4f} kg/m³" if rho_ref is not None else "—"
        self.lbl_status.setText(f"dp_ref={dp_ref:.0f}\" H₂O, ρ_ref={rho_txt}, A_ref={a_key}")

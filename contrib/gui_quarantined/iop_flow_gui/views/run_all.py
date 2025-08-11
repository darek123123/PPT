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
    QMessageBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Signal, Qt

from iop_flow.io_json import read_session
from iop_flow.api import run_all as run_all_api
from ..preferences import load_prefs

from ..widgets.mpl_canvas import MplCanvas
from ..wizard.state import lift_m_to_mm, q_m3s_to_cfm
from iop_flow import formulas as F


# Internal result keys (table data order)
COLS = [
    "lift_m",
    "q_m3s_ref",
    "A_ref_key",
    "Cd_ref",
    "V_ref",
    "Mach_ref",
    "SR",
]

# Display headers and tooltips
DISPLAY_COLS = [
    ("Lift [m]", "Skok zaworu; wartości z planu"),
    ("Q* [m³/s] @ ΔP_ref", "Przepływ przeliczony do ΔP_ref"),
    ("A_ref", "Pole referencyjne (throat/eff)"),
    ("Cd (-)", "Współczynnik wypływu przy ΔP_ref"),
    ("V_ref [m/s]", "Prędkość w polu referencyjnym"),
    ("Mach (-)", "Mach = V/a(T)"),
    ("SR [RPM]", "Swirl w RPM (jeśli dotyczy)"),
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

        # simple info button on the right
        info_row = QHBoxLayout()
        info_row.addStretch(1)
        btn_info = QPushButton("i", self)
        btn_info.setFixedWidth(24)
        btn_info.setToolTip("Co to jest?")
        btn_info.clicked.connect(self._show_info)
        info_row.addWidget(btn_info)
        lay.addLayout(info_row)

        # wiring
        self.btn_back.clicked.connect(lambda: self.back_requested.emit())
        self.btn_load.clicked.connect(self._on_load)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_save.clicked.connect(self._on_save)

        self._clear_views()
        self._refresh_buttons()

    def _show_info(self) -> None:
        QMessageBox.information(
            self,
            "Co to jest?",
            (
                "Cd (-) — Współczynnik wypływu przy ΔP_ref; Cd = Q / (A * sqrt(2ΔP/ρ)).\n"
                "Q [CFM]* — Przepływ przeliczony do ΔP_ref. W tabeli Q* w m³/s; na wykresie w CFM.\n"
                "Mach (-) — Mach = V/a(T). Tutaj V liczone z Q i pola referencyjnego."
            ),
        )

    def _refresh_buttons(self) -> None:
        has_session = self._session is not None
        self.btn_run.setEnabled(has_session)
        self.btn_save.setEnabled(self._result is not None)

    def _clear_views(self) -> None:
        # Clear tables
        empty_model = QStandardItemModel(0, len(COLS), self)
        empty_model.setHorizontalHeaderLabels([h for h, _ in DISPLAY_COLS])
        for i, (_, tip) in enumerate(DISPLAY_COLS):
            empty_model.setHeaderData(i, Qt.Horizontal, tip, role=Qt.ToolTipRole)
        self.tbl_int.setModel(empty_model)
        self.tbl_exh.setModel(empty_model)
        # Clear plots
        try:
            self.plot_cd.clear()
            self.plot_q.clear()
            self.plot_cd.render()
            self.plot_q.render()
        except Exception:
            pass

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Wczytaj Session JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            self._session = read_session(path)
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
        self._result = None
        self._clear_views()
        self._refresh_buttons()
        try:
            proj = getattr(self._session, "meta", {}).get("project_name", "") if self._session else ""
            msg = f"Wczytano Session{(': ' + proj) if proj else ''}"
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage(msg, 2500)
        except Exception:
            pass

    def _on_run(self) -> None:
        if self._session is None:
            return
        prefs = load_prefs()
        import time

        t0 = time.perf_counter()
        self._result = run_all_api(
            self._session,
            dp_ref_inH2O=(prefs.dp_ref_inH2O or 28.0),
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
        # write results only
        import json

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Błąd zapisu", f"Nie udało się zapisać wyników: {e}")
            return
        else:
            QMessageBox.information(self, "Zapisano", "Wyniki zapisane poprawnie.")
        try:
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage("Zapisano wyniki", 2000)
        except Exception:
            pass

    def _populate_tables(self) -> None:
        assert self._result is not None
        series = self._result["series"]
        self._fill_table(self.tbl_int, series.get("intake", []))
        self._fill_table(self.tbl_exh, series.get("exhaust", []))

    def _fill_table(self, tbl: QTableView, rows: List[Dict[str, Any]]) -> None:
        model = QStandardItemModel(len(rows), len(COLS), self)
        model.setHorizontalHeaderLabels([h for h, _ in DISPLAY_COLS])
        for i, (_, tip) in enumerate(DISPLAY_COLS):
            model.setHeaderData(i, Qt.Horizontal, tip, role=Qt.ToolTipRole)
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
        x_m = [row.get("lift_m", 0.0) for row in ints]
        a_key = None
        dp_ref = None
        rho_ref = None
        try:
            params = self._result.get("params", {})
            a_key = params.get("A_ref_key") or (ints[0].get("A_ref_key") if ints else "eff")
            dp_ref = float(params.get("dp_ref_inH2O", 28.0))
            # rho from current air
            if self._session and getattr(self._session, "air", None):
                air = self._session.air
                rho_ref = F.air_density(F.AirState(air.p_tot, air.T, air.RH))
        except Exception:
            pass
        x_mm = lift_m_to_mm(x_m)
        y_cd = [row.get("Cd_ref", 0.0) for row in ints]
        y_q_cfm = q_m3s_to_cfm([row.get("q_m3s_ref", 0.0) for row in ints])
        title_cd = f"Cd @ {a_key or 'eff'} ΔP={dp_ref or 28:.0f}\" H₂O"
        title_q = f"Q* @ {a_key or 'eff'} ΔP={dp_ref or 28:.0f}\" H₂O"
        self.plot_cd.set_readout_units("mm", "-")
        self.plot_q.set_readout_units("mm", "CFM")
        self.plot_cd.plot_xy(x_mm, y_cd, label="Cd_ref", xlabel="Lift [mm]", ylabel="Cd (-)", title=title_cd)
        self.plot_q.plot_xy(x_mm, y_q_cfm, label="q_m3s_ref", xlabel="Lift [mm]", ylabel="Q* [CFM]", title=title_q)
        self.plot_cd.render()
        self.plot_q.render()
        # show status in main window status bar
        try:
            win = self.window()
            if hasattr(win, "statusBar"):
                a_txt = str(a_key or "eff")
                rho_txt = f"{rho_ref:.4f} kg/m³" if rho_ref else "—"
                win.statusBar().showMessage(
                    f"dp_ref={dp_ref or 28:.0f}\" H₂O, ρ_ref={rho_txt}, A_ref={a_txt}", 4000
                )
        except Exception:
            pass

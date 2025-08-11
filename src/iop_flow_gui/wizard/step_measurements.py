from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QAbstractItemView,
)

from iop_flow.api import run_all
from iop_flow.schemas import Session

from .state import WizardState, parse_rows
from ..widgets.mpl_canvas import MplCanvas
from ..preferences import load_prefs


class _SideTable(QWidget):
    sig_changed = Signal()

    def __init__(self, state: WizardState, side: str) -> None:
        super().__init__()
        self.state = state
        self.side = side  # 'intake' | 'exhaust'

        lay = QVBoxLayout(self)
        btns = QHBoxLayout()
        lay.addLayout(btns)
        self.btn_autofill = QPushButton("Autouzupełnij lifty z planu", self)
        self.btn_copy_other = QPushButton("Skopiuj z drugiej zakładki", self)
        self.btn_clear = QPushButton("Wyczyść", self)
        btns.addWidget(self.btn_autofill)
        btns.addWidget(self.btn_copy_other)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"])
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        lay.addWidget(self.table)

        counts = QHBoxLayout()
        self.lbl_counts = QLabel("—", self)
        counts.addWidget(self.lbl_counts)
        counts.addStretch(1)
        lay.addLayout(counts)

        self.btn_autofill.clicked.connect(self._autofill)
        self.btn_copy_other.clicked.connect(self._copy_other)
        self.btn_clear.clicked.connect(self._clear)
        self.table.itemChanged.connect(self._on_changed)
        self.table.viewport().installEventFilter(self)

        self._load_from_state()
        self._update_counts()

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self.table.viewport() and event.type() == QEvent.KeyPress:
            ke: QKeyEvent = event  # type: ignore[assignment]
            if ke.matches(QKeySequence.Paste):
                self._paste_from_clipboard()
                return True
        return super().eventFilter(obj, event)

    def _load_from_state(self) -> None:
        rows = self.state.measure_intake if self.side == "intake" else self.state.measure_exhaust
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"]):
                val = row.get(key)
                self.table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.table.blockSignals(False)

    def _save_to_state(self) -> None:
        def parse_item(it: Optional[QTableWidgetItem]) -> Optional[float]:
            if it is None:
                return None
            s = (it.text() or "").strip()
            if s == "":
                return None
            try:
                # reuse parse_rows logic: comma and dot accepted
                from .state import parse_float_pl

                return parse_float_pl(s)
            except Exception:
                return None

        rows: List[Dict[str, Any]] = []
        seen: Dict[float, int] = {}
        for r in range(self.table.rowCount()):
            lift = parse_item(self.table.item(r, 0))
            q = parse_item(self.table.item(r, 1))
            dp = parse_item(self.table.item(r, 2))
            swirl = parse_item(self.table.item(r, 3))
            if lift is None or q is None:
                continue
            lift = round(max(lift, 0.0), 3)
            row: Dict[str, Any] = {"lift_mm": lift, "q_cfm": max(q, 0.0)}
            if dp is not None and dp > 0:
                row["dp_inH2O"] = dp
            if swirl is not None and swirl >= 0:
                row["swirl_rpm"] = swirl
            # keep last by lift
            if lift in seen:
                rows[seen[lift]] = row
            else:
                seen[lift] = len(rows)
                rows.append(row)
        rows.sort(key=lambda x: x["lift_mm"])  # sort increasing
        if self.side == "intake":
            self.state.measure_intake = rows
        else:
            self.state.measure_exhaust = rows

    def _apply_cell_validation(self) -> None:
        # Apply tooltip and background color on invalid cells
        def mark(item: Optional[QTableWidgetItem], good: bool, tip: str = "") -> None:
            if not item:
                return
            item.setToolTip("" if good else (tip or "Błędna wartość"))
            item.setBackground(Qt.white if good else Qt.red)  # type: ignore[arg-type]

        for r in range(self.table.rowCount()):
            it_l = self.table.item(r, 0)
            it_q = self.table.item(r, 1)
            it_dp = self.table.item(r, 2)
            it_sw = self.table.item(r, 3)

            def parse_opt(it: Optional[QTableWidgetItem]) -> Optional[float]:
                if it is None:
                    return None
                s = (it.text() or "").strip()
                if s == "":
                    return None
                try:
                    from .state import parse_float_pl

                    return parse_float_pl(s)
                except Exception:
                    return None

            l_v = parse_opt(it_l)
            q_v = parse_opt(it_q)
            dp_v = parse_opt(it_dp)
            sw_v = parse_opt(it_sw)
            mark(it_l, l_v is not None and l_v >= 0, ">= 0")
            mark(it_q, q_v is not None and q_v >= 0, ">= 0")
            mark(it_dp, dp_v is None or dp_v > 0, "> 0 lub puste")
            mark(it_sw, sw_v is None or sw_v >= 0, ">= 0 lub puste")

    def _update_counts(self) -> None:
        rows = self.state.measure_intake if self.side == "intake" else self.state.measure_exhaust
        n = len(rows)
        m = sum(1 for r in rows if r.get("dp_inH2O") is not None)
        k = sum(1 for r in rows if r.get("swirl_rpm") is not None)
        self.lbl_counts.setText(f"n: {n}, z dp: {m}, ze swirl: {k}")

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self._save_to_state()
        self._apply_cell_validation()
        self._update_counts()
        self.sig_changed.emit()

    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard().text()
        text = clipboard or ""
        rows = parse_rows(text)
        # Estimate bad rows: count non-empty logical lines with >=2 fields, then subtract parsed
        bad = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = [
                p.strip()
                for p in (line.split(";") if ";" in line else line.replace("\t", " ").split())
                if p
            ]
            if len(parts) >= 2:
                # candidate line; if parse_rows didn't include it, count as bad
                # crude heuristic: will be overcounted if duplicates trimmed; acceptable for toast
                bad += 1
        bad = max(0, bad - len(rows))
        if not rows:
            return
        start = self.table.rowCount()
        self.table.setRowCount(start + len(rows))
        for i, (lift, q, dp, swirl) in enumerate(rows):
            r = start + i
            vals = [lift, q, dp if dp is not None else "", swirl if swirl is not None else ""]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self._on_changed()
        # Show non-blocking toast in status bar if some lines were skipped
        if bad > 0:
            try:
                win = self.window()
                if hasattr(win, "statusBar"):
                    sb = win.statusBar()
                    if sb is not None:
                        sb.showMessage(f"Pominięto {bad} błędnych wierszy", 2500)
            except Exception:
                pass

    def _autofill(self) -> None:
        plan = self.state.plan_intake() if self.side == "intake" else self.state.plan_exhaust()
        if not plan:
            QMessageBox.information(self, "Plan", "Brak planu dla tej strony.")
            return
        rows_map: Dict[float, Dict[str, Any]] = {
            (row.get("lift_mm") or 0.0): dict(row)
            for row in (
                self.state.measure_intake if self.side == "intake" else self.state.measure_exhaust
            )
        }
        for lift in plan:
            if lift not in rows_map:
                rows_map[lift] = {"lift_mm": lift}
        merged = [rows_map[k] for k in sorted(rows_map.keys())]
        if self.side == "intake":
            self.state.measure_intake = merged
        else:
            self.state.measure_exhaust = merged
        self._load_from_state()
        self._update_counts()
        self.sig_changed.emit()

    def _copy_other(self) -> None:
        other = self.state.measure_exhaust if self.side == "intake" else self.state.measure_intake
        copied = [dict(r) for r in other]
        if self.side == "intake":
            self.state.measure_intake = copied
        else:
            self.state.measure_exhaust = copied
        self._load_from_state()
        self._update_counts()
        self.sig_changed.emit()

    def _clear(self) -> None:
        if self.side == "intake":
            self.state.measure_intake = []
        else:
            self.state.measure_exhaust = []
        self._load_from_state()
        self._update_counts()
        self.sig_changed.emit()



class StepMeasurements(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self._debounce = QTimer(self)
        self._debounce.setInterval(150)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._recompute)

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        self.tabs = QTabWidget(self)
        self.tab_intake = _SideTable(state, "intake")
        self.tab_exhaust = _SideTable(state, "exhaust")
        self.tab_intake.sig_changed.connect(self._on_changed)
        self.tab_exhaust.sig_changed.connect(self._on_changed)
        self.tabs.addTab(self.tab_intake, "INTAKE")
        self.tabs.addTab(self.tab_exhaust, "EXHAUST")
        self.tabs.currentChanged.connect(lambda _: self._recompute())
        left.addWidget(self.tabs)

        actions = QHBoxLayout()
        self.btn_compute = QPushButton("Przelicz", self)
        self.btn_back = QPushButton("Wstecz", self)
        self.btn_next = QPushButton("Dalej", self)
        actions.addWidget(self.btn_compute)
        actions.addStretch(1)
        actions.addWidget(self.btn_back)
        actions.addWidget(self.btn_next)
        left.addLayout(actions)

        right = QVBoxLayout()
        self.plot_cd = MplCanvas()
        self.plot_q = MplCanvas()
        right.addWidget(QLabel("Cd_ref vs lift_m", self))
        right.addWidget(self.plot_cd)
        right.addWidget(QLabel("q_m3s_ref vs lift_m", self))
        right.addWidget(self.plot_q)
        self.lbl_params = QLabel("—", self)
        right.addWidget(self.lbl_params)
        self.lbl_ei = QLabel("", self)
        right.addWidget(self.lbl_ei)

        root.addLayout(left, 2)
        root.addLayout(right, 3)

        self.btn_compute.clicked.connect(self._recompute)
        self._on_changed()
        QTimer.singleShot(0, self._recompute)

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self.btn_compute.setEnabled(True)
        self._debounce.start()
        self._emit_valid()

    def _emit_valid(self) -> None:
        ok_prev = self._prev_steps_ok()
        ok_data = (len(self.state.measure_intake) > 0) or (len(self.state.measure_exhaust) > 0)
        self.sig_valid_changed.emit(bool(ok_prev and ok_data))

    def _prev_steps_ok(self) -> bool:
        from .state import is_valid_step_bench, is_valid_step_geometry

        return is_valid_step_bench(self.state) and is_valid_step_geometry(self.state)

    def _recompute(self) -> None:
        if not self._prev_steps_ok():
            return
        if not (self.state.measure_intake or self.state.measure_exhaust):
            try:
                self.plot_cd.clear()
                self.plot_q.clear()
                self.plot_cd.render()
                self.plot_q.render()
                self.lbl_params.setText("—")
                self.lbl_ei.setText("")
            except Exception:
                pass
            return
        try:
            session: Session = self.state.build_session_from_wizard_for_compute()
        except Exception:
            return
        prefs = load_prefs()
        import time

        t0 = time.perf_counter()
        try:
            result = run_all(
                session,
                dp_ref_inH2O=(prefs.dp_ref_inH2O or 28.0),
                a_ref_mode=prefs.a_ref_mode,
                eff_mode=prefs.eff_mode,
            )
        except Exception:
            try:
                self.plot_cd.clear()
                self.plot_q.clear()
                self.plot_cd.render()
                self.plot_q.render()
                self.lbl_params.setText("—")
                self.lbl_ei.setText("")
                win = self.window()
                if hasattr(win, "statusBar"):
                    sb = win.statusBar()
                    if sb is not None:
                        sb.showMessage("Błąd obliczeń (pomiń do czasu uzupełnienia danych)", 2500)
            except Exception:
                pass
            return
        series = result.get("series", {})
        active_idx = self.tabs.currentIndex()
        side = "intake" if active_idx == 0 else "exhaust"
        data: List[Dict[str, Any]] = series.get(side, [])  # type: ignore[assignment]

        self.plot_cd.clear()
        self.plot_q.clear()
        lifts = [d.get("lift_m") for d in data]
        cd = [d.get("Cd_ref") for d in data]
        q = [d.get("q_m3s_ref") for d in data]
        label_side = "INT" if side == "intake" else "EXH"
        if lifts and any(v is not None for v in cd):
            self.plot_cd.plot_xy(lifts, cd, label=f"{label_side} Cd_ref")
        if lifts and any(v is not None for v in q):
            self.plot_q.plot_xy(lifts, q, label=f"{label_side} q_m3s_ref")
        self.plot_cd.render()
        self.plot_q.render()

        rho_ref = None
        try:
            from iop_flow import formulas as F

            rho_ref = (
                F.air_density(F.AirState(self.state.air.p_tot, self.state.air.T, self.state.air.RH))
                if self.state.air
                else None
            )
        except Exception:
            rho_ref = None
        params_txt = (
            f'dp_ref={self.state.air_dp_ref_inH2O:.1f}"H₂O, '
            f"ρ_ref={rho_ref:.4f} kg/m³, A_ref_mode=eff, eff_mode=smoothmin"
            if rho_ref is not None
            else f'dp_ref={self.state.air_dp_ref_inH2O:.1f}"H₂O, A_ref_mode=eff, eff_mode=smoothmin'
        )
        self.lbl_params.setText(params_txt)

        ei_text = ""
        if series.get("ei"):
            ei = series["ei"]
            if ei:
                vals = [e.get("EI") for e in ei if e.get("EI") is not None]
                if vals:
                    ei_text = f"E/I avg={sum(vals) / len(vals):.3f} min={min(vals):.3f} max={max(vals):.3f}"
        self.lbl_ei.setText(ei_text)

        try:
            sr_vals = [d.get("SR") for d in data if d.get("SR") is not None]
            sr_txt = f"{sum(sr_vals) / len(sr_vals):.0f} rpm" if sr_vals else "—"
            self.lbl_params.setText(self.lbl_params.text() + f", SR_avg={sr_txt}")
        except Exception:
            pass
        self.btn_compute.setEnabled(False)
        try:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            win = self.window()
            if hasattr(win, "statusBar"):
                sb = win.statusBar()
                if sb is not None:
                    sb.showMessage(f"OK ({dt_ms} ms)", 2000)
        except Exception:
            pass
        self._emit_valid()

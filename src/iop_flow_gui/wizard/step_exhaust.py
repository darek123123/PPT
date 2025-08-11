from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal, QEvent, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)

from iop_flow.api import run_all
from .state import WizardState, parse_rows
from ..widgets.mpl_canvas import MplCanvas


class StepExhaust(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

        root = QHBoxLayout(self)

        # Left: controls and table
        left = QVBoxLayout()
        btns = QHBoxLayout()
        self.btn_autofill = QPushButton("Autouzupełnij lifty z planu EXH", self)
        self.btn_copy_from_int = QPushButton("Skopiuj INT → EXH (tylko lift)", self)
        self.btn_clear = QPushButton("Wyczyść", self)
        btns.addWidget(self.btn_autofill)
        btns.addWidget(self.btn_copy_from_int)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)
        left.addLayout(btns)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"])
        from PySide6.QtWidgets import QAbstractItemView
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.table.viewport().installEventFilter(self)
        left.addWidget(self.table)

        counts = QHBoxLayout()
        self.lbl_counts = QLabel("—", self)
        counts.addWidget(self.lbl_counts)
        counts.addStretch(1)
        left.addLayout(counts)

        actions = QHBoxLayout()
        self.btn_compute = QPushButton("Przelicz", self)
        self.btn_back = QPushButton("Wstecz", self)
        self.btn_next = QPushButton("Dalej", self)
        actions.addWidget(self.btn_compute)
        actions.addStretch(1)
        actions.addWidget(self.btn_back)
        actions.addWidget(self.btn_next)
        left.addLayout(actions)

        root.addLayout(left, 2)

        # Right: E/I results
        right = QVBoxLayout()
        # Info row with corner notice
        info_row = QHBoxLayout()
        info_row.addStretch(1)
        from PySide6.QtWidgets import QToolButton

        self.btn_info = QToolButton(self)
        self.btn_info.setText("i")
        self.btn_info.setToolTip("Informacje o wskaźniku E/I")
        self.btn_info.clicked.connect(self._show_info)
        info_row.addWidget(self.btn_info)
        right.addLayout(info_row)

        self.plot_ei = MplCanvas()
        self.plot_ei.set_readout_units("mm", "-")
        right.addWidget(self.plot_ei)
        self.lbl_ei = QLabel("—", self)
        self.lbl_alert = QLabel("", self)
        self.lbl_alert.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_corner = QLabel("", self)
        self.lbl_corner.setStyleSheet("color: #a00; font-style: italic;")
        self.lbl_corner.setAlignment(Qt.AlignRight)
        right.addWidget(self.lbl_ei)
        right.addWidget(self.lbl_alert)
        right.addWidget(self.lbl_corner)

        root.addLayout(right, 3)

        # Wire
        self.btn_autofill.clicked.connect(self._autofill)
        self.btn_copy_from_int.clicked.connect(self._copy_intake_lifts)
        self.btn_clear.clicked.connect(self._clear)
        self.table.itemChanged.connect(self._on_changed)
        self.btn_compute.clicked.connect(self._compute)

        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self.table.viewport() and event.type() == QEvent.KeyPress:
            ke: QKeyEvent = event  # type: ignore[assignment]
            if ke.matches(QKeySequence.Paste):
                self._paste_from_clipboard()
                return True
        return super().eventFilter(obj, event)

    def _load_from_state(self) -> None:
        rows = self.state.measure_exhaust
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
            if lift in seen:
                rows[seen[lift]] = row
            else:
                seen[lift] = len(rows)
                rows.append(row)
        rows.sort(key=lambda x: x["lift_mm"])  # sort increasing
        self.state.measure_exhaust = rows

    def _update_counts(self) -> None:
        rows = self.state.measure_exhaust
        n = len(rows)
        m = sum(1 for r in rows if r.get("dp_inH2O") is not None)
        k = sum(1 for r in rows if r.get("swirl_rpm") is not None)
        self.lbl_counts.setText(f"n: {n}, z dp: {m}, ze swirl: {k}")

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self._save_to_state()
        self._update_counts()
        self._emit_valid()

    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard().text()
        rows = parse_rows(clipboard or "")
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

    def _autofill(self) -> None:
        plan = list(self.state.plan_exhaust())
        if not plan:
            QMessageBox.information(self, "Plan EXH", "Brak planu dla EXH.")
            return
        rows_map: Dict[float, Dict[str, Any]] = {
            (row.get("lift_mm") or 0.0): dict(row) for row in self.state.measure_exhaust
        }
        for lift in plan:
            if lift not in rows_map:
                rows_map[lift] = {"lift_mm": lift}
        self.state.measure_exhaust = [rows_map[k] for k in sorted(rows_map.keys())]
        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def _copy_intake_lifts(self) -> None:
        rows_int = self.state.measure_intake
        lifts = sorted({round(float(r.get("lift_mm", 0.0)), 3) for r in rows_int})
        mapped = [{"lift_mm": lift_val} for lift_val in lifts]
        self.state.measure_exhaust = mapped
        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def _clear(self) -> None:
        self.state.measure_exhaust = []
        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def _emit_valid(self) -> None:
        # Allow Next even if exhaust empty (user can skip)
        self.sig_valid_changed.emit(True)

    def _compute(self) -> None:
        try:
            session = self.state.build_session_for_run_all()
        except Exception:
            return
        result = run_all(
            session,
            dp_ref_inH2O=self.state.air_dp_ref_inH2O or 28.0,
            a_ref_mode="eff",
            eff_mode="smoothmin",
            engine_v_target=(self.state.engine_v_target or 100.0),
        )
        series = result.get("series", {})
        intake: List[Dict[str, Any]] = series.get("intake", [])  # type: ignore[assignment]
        exhaust: List[Dict[str, Any]] = series.get("exhaust", [])  # type: ignore[assignment]
        ei = series.get("ei", [])

        # Plot E/I vs lift for matched lifts only
        self.plot_ei.clear()
        if ei:
            lifts_m = [float(row.get("lift_m") or 0.0) for row in ei]
            lifts_mm = [v * 1000.0 for v in lifts_m]
            vals = [row.get("EI") for row in ei]
            valid_vals = [float(v) for v in vals if v is not None]
            title_extra = f" · mean={sum(valid_vals)/len(valid_vals):.3f}" if valid_vals else ""
            if lifts_mm and any(v is not None for v in vals):
                self.plot_ei.plot_xy(
                    lifts_mm,
                    [float(v) if v is not None else 0.0 for v in vals],
                    label="E/I",
                    xlabel="Lift [mm]",
                    ylabel="E/I [–]",
                    title=f"E/I vs Lift{title_extra}",
                )
        self.plot_ei.render()

        # Summary and alerts
        txt = ""
        if intake and exhaust:
            txt = f"INT={len(intake)} EXH={len(exhaust)} dopasowane={len(ei)}"
            if ei:
                valid = [x.get("EI") for x in ei if x.get("EI") is not None]
                if valid:
                    avg = sum(valid) / len(valid)
                    txt += f"; mean(E/I)={avg:.3f}"
                    if avg < 0.70 or avg > 0.85:
                        self.lbl_alert.setText("ALERT: E/I poza zakresem 0.70–0.85")
                    else:
                        self.lbl_alert.setText("")
                else:
                    self.lbl_alert.setText("")
            self.lbl_corner.setText("")
        else:
            txt = "Brak danych exhaust — E/I będzie puste"
            self.lbl_alert.setText("")
            self.lbl_corner.setText("Brak danych wydechu — wykres niedostępny (INFO)")
        self.lbl_ei.setText(txt)

    def _show_info(self) -> None:
        QMessageBox.information(
            self,
            "E/I — co to jest?",
            (
                "E/I to stosunek przepływu wydechu do ssania dla tych samych liftów.\n"
                "Wykres pokazuje E/I w funkcji liftu [mm].\n\n"
                "Uwaga: jeśli brak danych EXH, wykres jest niedostępny."
            ),
        )

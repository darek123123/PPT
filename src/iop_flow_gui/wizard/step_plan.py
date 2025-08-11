from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
)

from ..widgets.mpl_canvas import MplCanvas
from .state import WizardState, parse_float_pl, gen_grid, set_plan_from_ui, is_valid_step_plan


class StepPlan(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

        root = QHBoxLayout(self)

        # left: grid generator
        left = QVBoxLayout()
        root.addLayout(left, 1)
        form = QFormLayout()
        left.addLayout(form)
        self.ed_start = QLineEdit(self)
        self.ed_stop = QLineEdit(self)
        self.ed_step = QLineEdit(self)
        form.addRow("Start [mm]", self.ed_start)
        form.addRow("Stop [mm]", self.ed_stop)
        form.addRow("Step [mm]", self.ed_step)
        # action row
        row_buttons = QHBoxLayout()
        left.addLayout(row_buttons)
        self.btn_gen_i = QPushButton("Generuj (INT)", self)
        self.btn_gen_e = QPushButton("Generuj (EXH)", self)
        self.btn_copy = QPushButton("Skopiuj INT → EXH", self)
        self.btn_clear = QPushButton("Wyczyść", self)
        row_buttons.addWidget(self.btn_gen_i)
        row_buttons.addWidget(self.btn_gen_e)
        row_buttons.addWidget(self.btn_copy)
        row_buttons.addWidget(self.btn_clear)

        self.chk_swirl = QPushButton("Będę wpisywać swirl (RPM)", self)
        self.chk_swirl.setCheckable(True)
        left.addWidget(self.chk_swirl)

        # right: tabs for tables + plot + counts
        right = QVBoxLayout()
        root.addLayout(right, 1)
        self.tabs = QTabWidget(self)
        right.addWidget(self.tabs)
        self.tbl_i = QTableWidget(self)
        self.tbl_e = QTableWidget(self)
        for tbl in (self.tbl_i, self.tbl_e):
            tbl.setColumnCount(2)
            tbl.setHorizontalHeaderLabels(["lift_mm", "dp_inH2O"])
            tbl.setRowCount(0)
        self.tabs.addTab(self.tbl_i, "INT")
        self.tabs.addTab(self.tbl_e, "EXH")

        self.lbl_counts = QLabel("INT: 0, EXH: 0", self)
        right.addWidget(self.lbl_counts)
        self.plot = MplCanvas()
        right.addWidget(self.plot)

        # wiring
        self.btn_gen_i.clicked.connect(lambda: self._gen("intake"))
        self.btn_gen_e.clicked.connect(lambda: self._gen("exhaust"))
        self.btn_copy.clicked.connect(self._copy_int_to_exh)
        self.btn_clear.clicked.connect(self._clear)
        self.tbl_i.itemChanged.connect(lambda *_: self._on_changed())
        self.tbl_e.itemChanged.connect(lambda *_: self._on_changed())
        self.chk_swirl.toggled.connect(lambda *_: self._on_changed())
        # Prefill from state if present; otherwise generate 1..9 mm
        self._prefill_from_state()
        self._on_changed()

    def _grid_inputs(self) -> Optional[Tuple[float, float, float]]:
        try:
            s = parse_float_pl(self.ed_start.text())
            e = parse_float_pl(self.ed_stop.text())
            st = parse_float_pl(self.ed_step.text())
            return (s, e, st)
        except Exception:
            return None

    def _gen(self, side: str) -> None:
        vals: List[float] = []
        g = self._grid_inputs()
        if g:
            vals = gen_grid(*g)
        self._fill_table(self.tbl_i if side == "intake" else self.tbl_e, vals)
        self._on_changed()

    def _copy_int_to_exh(self) -> None:
        self._fill_table(self.tbl_e, self._read_table(self.tbl_i)[0])
        self._on_changed()

    def _clear(self) -> None:
        self._fill_table(self.tbl_i, [])
        self._fill_table(self.tbl_e, [])
        self._on_changed()

    def _prefill_from_state(self) -> None:
        li = list(self.state.plan_intake())
        le = list(self.state.plan_exhaust())
        if not li:
            li = [float(x) for x in range(1, 10)]
        if not le:
            le = [float(x) for x in range(1, 10)]
        self._fill_table(self.tbl_i, li)
        self._fill_table(self.tbl_e, le)
        # Fill dp where present in state
        def _apply_dp(tbl: QTableWidget, side: str) -> None:
            for r in range(tbl.rowCount()):
                it_l = tbl.item(r, 0)
                if not it_l:
                    continue
                try:
                    lift = round(parse_float_pl(it_l.text()), 3)
                except Exception:
                    continue
                dp = self.state.dp_for_point(side, lift)
                if dp is not None:
                    tbl.setItem(r, 1, QTableWidgetItem(f"{dp:.3f}"))
        _apply_dp(self.tbl_i, "intake")
        _apply_dp(self.tbl_e, "exhaust")


    def _fill_table(self, tbl: QTableWidget, lifts: List[float]) -> None:
        tbl.blockSignals(True)
        try:
            tbl.setRowCount(len(lifts))
            for r, v in enumerate(lifts):
                item_l = QTableWidgetItem(f"{v:.3f}")
                item_dp = QTableWidgetItem("")
                tbl.setItem(r, 0, item_l)
                tbl.setItem(r, 1, item_dp)
        finally:
            tbl.blockSignals(False)

    def _read_table(self, tbl: QTableWidget) -> Tuple[List[float], Dict[float, float]]:
        lifts: List[float] = []
        dp_map: Dict[float, float] = {}
        for r in range(tbl.rowCount()):
            l_item = tbl.item(r, 0)
            d_item = tbl.item(r, 1)
            if not l_item:
                continue
            try:
                lift = round(parse_float_pl(l_item.text()), 3)
            except Exception:
                continue
            lifts.append(lift)
            if d_item and d_item.text().strip():
                try:
                    dp = parse_float_pl(d_item.text())
                    if dp > 0:
                        dp_map[lift] = dp
                except Exception:
                    pass
        # sort and dedupe, keep last dp
        lifts = sorted(set(lifts))
        return lifts, dp_map

    def _update_counts(self) -> None:
        li, _ = self._read_table(self.tbl_i)
        le, _ = self._read_table(self.tbl_e)
        self.lbl_counts.setText(f"INT: {len(li)}, EXH: {len(le)}")

    def _update_plot(self) -> None:
        self.plot.clear()
        g = self.state.geometry
        li, _ = self._read_table(self.tbl_i)
        le, _ = self._read_table(self.tbl_e)
        if g and li:
            x = li
            y_i = [(lift / 1000.0) / g.valve_int_m for lift in li]
            self.plot.plot_xy(x, y_i, label="L/D INT")
        if g and le:
            y_e = [(lift / 1000.0) / g.valve_exh_m for lift in le]
            self.plot.plot_xy(le, y_e, label="L/D EXH")
        self.plot.render()

    def _on_changed(self) -> None:
        self._update_counts()
        self._update_plot()
        # save into state
        li, dpi = self._read_table(self.tbl_i)
        le, dpe = self._read_table(self.tbl_e)
        dp_map: Dict[Tuple[str, float], float] = {}
        for lift, v in dpi.items():
            dp_map[("intake", lift)] = v
        for lift, v in dpe.items():
            dp_map[("exhaust", lift)] = v
        set_plan_from_ui(
            self.state,
            intake=li,
            exhaust=le,
            dp_map=dp_map,
            will_swirl=self.chk_swirl.isChecked(),
        )
        ok = is_valid_step_plan(self.state)
        self.sig_valid_changed.emit(ok)

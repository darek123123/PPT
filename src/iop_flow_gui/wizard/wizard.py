from __future__ import annotations

import os
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QLabel,
    QFileDialog,
    QMenuBar,
)
from PySide6.QtGui import QAction

from .state import (
    WizardState,
    is_valid_step_start,
    is_valid_step_bench,
    is_valid_step_engine,
    is_valid_step_geometry,
    is_valid_step_plan,
)
from .step_start import StepStart
from .step_bench import StepBench
from .step_engine import StepEngine
from .step_geometry import StepGeometry
from .step_plan import StepPlan
from .step_measurements import StepMeasurements
from .step_csa import StepCSA
from .step_exhaust import StepExhaust
from .step_validate import StepValidate
from .step_report import StepReport


class WizardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nowa sesja — kreator")
        self.state = WizardState()
        self.settings = QSettings("iop-flow", "wizard")
        self._expert_mode = bool(self.settings.value("expert_mode", False))

        # menu
        mb = QMenuBar(self)
        self.setMenuBar(mb)
        menu_app = mb.addMenu("Aplikacja")
        act_prefs = QAction("Ustawienia…", self)
        act_expert = QAction("Tryb Ekspert", self)
        act_expert.setCheckable(True)
        act_expert.setChecked(self._expert_mode)
        menu_app.addAction(act_prefs)
        menu_app.addSeparator()
        menu_app.addAction(act_expert)

        central = QWidget(self)
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        # breadcrumb + progress
        self.lbl_breadcrumb = QLabel(
            "Start → Bench & Air → Silnik → Geometria → Plan → Pomiary → CSA → Exhaust → Walidacja → Raport",
            self,
        )
        root.addWidget(self.lbl_breadcrumb)

        self.stack = QStackedWidget(self)
        root.addWidget(self.stack)

        # steps
        self.step1 = StepStart(self.state)
        self.step2 = StepBench(self.state)
        self.step3 = StepEngine(self.state)
        self.step4 = StepGeometry(self.state)
        self.step5 = StepPlan(self.state)
        self.step6 = StepMeasurements(self.state)
        self.step7 = StepCSA(self.state)
        self.step8 = StepExhaust(self.state)
        self.step9 = StepValidate(self.state)
        self.step10 = StepReport(self.state)

        for w in (
            self.step1,
            self.step2,
            self.step3,
            self.step4,
            self.step5,
            self.step6,
            self.step7,
            self.step8,
            self.step9,
            self.step10,
        ):
            self.stack.addWidget(w)

        # nav
        nav = QHBoxLayout()
        root.addLayout(nav)
        self.btn_back = QPushButton("Wstecz", self)
        self.btn_next = QPushButton("Dalej", self)
        self.btn_save = QPushButton("Zapisz szkic…", self)
        self.btn_close = QPushButton("Zamknij", self)
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        nav.addStretch(1)
        nav.addWidget(self.btn_save)
        nav.addWidget(self.btn_close)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_close.clicked.connect(self.close)
        self.btn_save.clicked.connect(self._save_draft)
        act_prefs.triggered.connect(self._open_prefs)
        act_expert.toggled.connect(self._toggle_expert)

        # validity wiring
        for s in (
            self.step1,
            self.step2,
            self.step3,
            self.step4,
            self.step5,
            self.step6,
            self.step7,
            self.step8,
        ):
            s.sig_valid_changed.connect(lambda ok: self._update_nav())
        # steps 9 and 10 don't gate Next (end of wizard)

        self._update_nav()

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.btn_back.setEnabled(idx > 0)
        if self._expert_mode:
            self.btn_next.setEnabled(idx < (self.stack.count() - 1))
            return
        allow_next = False
        if idx == 0:
            allow_next = is_valid_step_start(self.state)
        elif idx == 1:
            allow_next = is_valid_step_bench(self.state)
        elif idx == 2:
            allow_next = is_valid_step_engine(self.state)
        elif idx == 3:
            allow_next = is_valid_step_geometry(self.state)
        elif idx == 4:
            allow_next = is_valid_step_plan(self.state)
        elif idx == 5:
            ok_prev = (
                is_valid_step_plan(self.state)
                and is_valid_step_geometry(self.state)
                and is_valid_step_bench(self.state)
            )
            has_rows = bool(self.state.measure_intake or self.state.measure_exhaust)
            allow_next = bool(ok_prev and has_rows)
        elif idx == 6:
            # CSA optional
            allow_next = True
        elif idx == 7:
            # Exhaust step: allow next even if empty, but if present validate basic intake/exhaust presence
            allow_next = True
        elif idx in (8, 9):
            allow_next = idx < (self.stack.count() - 1)
        self.btn_next.setEnabled(allow_next)

    def _go_back(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _go_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._update_nav()

    def _save_draft(self) -> None:
        last_dir = self.settings.value("last_dir", "", type=str) or ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz szkic", last_dir, "Draft (*.draft.json)"
        )
        if not path:
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        # status bar OK
        try:
            self.statusBar().showMessage("OK", 2000)
        except Exception:
            pass

    def _open_prefs(self) -> None:
        from ..preferences import PreferencesDialog

        dlg = PreferencesDialog()
        if dlg.exec() == dlg.Accepted:
            # Propagate any dynamic UI that depends on prefs
            # Step components can re-read as needed on next compute
            try:
                self.statusBar().showMessage("OK", 2000)
            except Exception:
                pass

    def _toggle_expert(self, on: bool) -> None:
        self._expert_mode = bool(on)
        self.settings.setValue("expert_mode", self._expert_mode)
        self._update_nav()

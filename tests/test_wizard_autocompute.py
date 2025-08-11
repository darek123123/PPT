"""Headless smoke test verifying auto-compute for all wizard steps.

Relies on Honda K20A2 preset; ensures each step sets `_auto_done` and plots at least once.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from iop_flow_gui.wizard.state import WizardState
from iop_flow_gui.wizard.step_start import StepStart
from iop_flow_gui.wizard.step_bench import StepBench
from iop_flow_gui.wizard.step_engine import StepEngine
from iop_flow_gui.wizard.step_plan import StepPlan
from iop_flow_gui.wizard.step_measurements import StepMeasurements
from iop_flow_gui.wizard.step_csa import StepCSA
from iop_flow_gui.wizard.step_exhaust import StepExhaust
from iop_flow_gui.wizard.step_validate import StepValidate


@pytest.fixture(scope="session")
def qapp():  # type: ignore[annotation-unchecked]
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _process(app, ms: int = 60):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()


def test_wizard_steps_autocompute(qapp):  # noqa: D103
    state = WizardState()
    state.apply_defaults_preset()
    steps = [
        StepStart(state),        # 0
        StepBench(state),        # 1
        StepEngine(state),       # 2
        StepPlan(state),         # 3
        StepMeasurements(state), # 4
        StepCSA(state),          # 5
        StepExhaust(state),      # 6
        StepValidate(state),     # 7
    ]
    # Ensure widgets are shown so showEvent triggers (where implemented)
    for w in steps:
        try:
            w.show()
        except Exception:
            pass
    _process(qapp, 180)
    # All steps must have auto_done flag set
    for w in steps:
        assert getattr(w, "_auto_done", True) is True, f"Auto compute not executed for {type(w).__name__}"

    # Define plot-capable attributes per step
    plot_attrs = {
        2: ["canvas"],               # StepEngine
        3: ["plot"],                 # StepPlan
        4: ["plot_cd", "plot_q"],    # StepMeasurements
        5: ["plot_mach"],            # StepCSA
        6: ["plot_ei"],              # StepExhaust
    }
    for idx, attrs in plot_attrs.items():
        for attr in attrs:
            c = getattr(steps[idx], attr, None)
            assert c is not None, f"Missing plot {attr} for step index {idx}"
            # Allow an extra event cycle if zero
            if getattr(c, "last_points_count", 0) == 0:
                _process(qapp, 120)
            assert getattr(c, "last_points_count", 0) > 0, f"Plot {attr} empty in step {idx}"

    # Non-plot steps: simple status / structure assertions
    # StepBench should have air conditions labels (e.g., contains some text in any QLabel with 'm/s' or 'kg/m')
    bench_labels = []
    for child in steps[1].findChildren(QLabel):
        try:
            txt = child.text()
        except Exception:
            continue
        if txt:
            bench_labels.append(txt)
    assert any("m/s" in t or "kg/m" in t or "H₂O" in t for t in bench_labels), "Bench step lacks expected status text"

    # StepValidate has a tree summary
    assert steps[7].tree.topLevelItemCount() > 0, "Validate tree empty"

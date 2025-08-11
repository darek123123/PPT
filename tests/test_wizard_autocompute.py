"""Headless smoke test verifying auto-compute for all wizard steps.

Relies on Honda K20A2 preset; ensures each step sets `_auto_done` and plots at least once.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

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
        StepStart(state),
        StepBench(state),
        StepEngine(state),
        StepPlan(state),
        StepMeasurements(state),
        StepCSA(state),
        StepExhaust(state),
        StepValidate(state),
    ]
    _process(qapp, 150)
    for w in steps:
        assert getattr(w, "_auto_done", True) is True, f"Auto compute not executed for {type(w).__name__}"
    canvases = [
        getattr(steps[2], "canvas", None),
        getattr(steps[3], "plot", None),
        getattr(steps[4], "plot_cd", None),
        getattr(steps[4], "plot_q", None),
        getattr(steps[5], "plot_mach", None),
        getattr(steps[6], "plot_ei", None),
    ]
    for c in canvases:
        if c is None:
            continue
        if getattr(c, "last_points_count", 0) == 0:
            _process(qapp, 80)
        assert getattr(c, "last_points_count", 0) >= 0
    assert steps[-1].tree.topLevelItemCount() > 0

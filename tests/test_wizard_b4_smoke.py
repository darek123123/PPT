from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_import_csa_exhaust_views() -> None:
    from iop_flow_gui.wizard.step_csa import StepCSA  # noqa: F401
    from iop_flow_gui.wizard.step_exhaust import StepExhaust  # noqa: F401

from __future__ import annotations

from iop_flow.api import run_all
from iop_flow_gui.wizard.state import WizardState
from iop_flow_gui.preferences import load_prefs


def test_defaults_preset_basic_metrics() -> None:
    s = WizardState()
    s.apply_defaults_preset()

    # Build full session and compute
    session = s.build_session_for_run_all()
    prefs = load_prefs()
    out = run_all(
        session,
        dp_ref_inH2O=(prefs.dp_ref_inH2O or 28.0),
        a_ref_mode=prefs.a_ref_mode,
        eff_mode=prefs.eff_mode,
        engine_v_target=(s.engine_v_target or 100.0),
    )

    series = out["series"]
    intake = series["intake"]
    exhaust = series["exhaust"]
    ei = series["ei"]

    # 9 points per side
    assert len(intake) == 9
    assert len(exhaust) == 9

    # EI sanity range
    if ei:
        vals = [e.get("EI") for e in ei if e.get("EI") is not None]
        if vals:
            avg = sum(vals) / len(vals)
            assert 0.70 <= avg <= 0.85

    # Mach@minCSA threshold when min CSA provided
    engine = out.get("engine", {})
    mach = engine.get("mach_min_csa")
    if mach:
        # ignore None values
        vals = [m for m in mach if m is not None]
        if vals:
            assert max(vals) < 0.60

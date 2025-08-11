from __future__ import annotations

import json
from pathlib import Path

from iop_flow_gui.wizard.state import WizardState
from iop_flow.io_json import read_session


def test_wizard_state_tuning_in_dict(tmp_path: Path) -> None:
    s = WizardState()
    s.apply_defaults_preset()
    s.tuning = {"intake_calc": {"L_mm": 300.0}, "foo": 123}
    d = s.to_dict()
    assert "tuning" in d
    assert isinstance(d["tuning"], dict)
    assert d["tuning"]["intake_calc"]["L_mm"] == 300.0
    assert d["tuning"]["foo"] == 123

    # Build a Session dict and write/read roundtrip; ensure reader maps tuning
    session_data = s.build_session_for_run_all().to_dict()
    session_data["tuning"] = s.tuning
    p = tmp_path / "session.json"
    p.write_text(json.dumps(session_data), encoding="utf-8")
    loaded = read_session(p)
    assert loaded.tuning is not None
    assert loaded.tuning.get("intake_calc", {}).get("L_mm") == 300.0
    assert loaded.tuning.get("foo") == 123

    # WizardState.from_dict should preserve unknown tuning keys
    ws2 = WizardState.from_dict({"tuning": s.tuning})
    assert ws2.tuning.get("intake_calc", {}).get("L_mm") == 300.0
    assert ws2.tuning.get("foo") == 123

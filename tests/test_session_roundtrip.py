from __future__ import annotations

from pathlib import Path

from iop_flow.io_json import write_session, read_session
from iop_flow_gui.wizard.state import WizardState


def test_session_io_roundtrip(tmp_path: Path) -> None:
    s = WizardState()
    s.apply_defaults_preset()
    session = s.build_session_for_run_all()
    p = tmp_path / "session.json"
    write_session(p, session)
    loaded = read_session(p)
    assert loaded.engine.displ_L == session.engine.displ_L
    assert len(loaded.lifts.intake) == len(session.lifts.intake)
    assert len(loaded.lifts.exhaust) == len(session.lifts.exhaust)

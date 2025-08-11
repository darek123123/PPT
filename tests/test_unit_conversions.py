from __future__ import annotations

from iop_flow_gui.wizard.state import lift_m_to_mm, q_m3s_to_cfm


def test_lift_m_to_mm():
    assert lift_m_to_mm([0.0, 0.001, 0.010]) == [0.0, 1.0, 10.0]


def test_q_m3s_to_cfm():
    vals = q_m3s_to_cfm([0.0, 0.01])
    assert isinstance(vals, list) and len(vals) == 2
    # 0.01 m^3/s ≈ 21.1888 CFM
    assert abs(vals[1] - 21.1888) < 0.1

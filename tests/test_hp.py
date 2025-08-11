from __future__ import annotations

from iop_flow.hp import hp_from_mass_air, hp_from_cfm
from iop_flow.formulas import CFM_TO_M3S


def approx_equal(a: float, b: float, tol_pct: float = 5.0) -> bool:
    return abs(a - b) <= (tol_pct / 100.0) * max(1.0, abs(b))


def test_hp_from_mass_air_300cfm() -> None:
    # 300 CFM total, rho_ref ~ 1.204 kg/m^3 @ 20C
    q_m3s = 300.0 * CFM_TO_M3S
    rho = 1.204
    m_air = rho * q_m3s  # kg/s
    hp = hp_from_mass_air(m_air, afr=12.5, bsfc_lb_hph=0.50)
    assert approx_equal(hp, 216.0, 5.0)


def test_hp_from_cfm_rule_of_thumb_280cfm() -> None:
    hp = hp_from_cfm(280.0, cfm_per_hp=1.67)
    assert approx_equal(hp, 168.0, 5.0)

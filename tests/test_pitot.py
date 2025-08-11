from __future__ import annotations

from iop_flow.formulas import velocity_pitot, speed_of_sound, C_to_K


def test_pitot_velocity_and_mach() -> None:
    dp = 100.0  # Pa
    rho = 1.2   # kg/m^3
    V = velocity_pitot(dp, rho, c_probe=1.0)
    assert 12.5 < V < 13.3  # ~12.91 m/s
    a = speed_of_sound(C_to_K(20.0))
    Mach = V / a
    assert 0.035 < Mach < 0.041  # ~0.038

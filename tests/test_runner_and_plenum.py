from __future__ import annotations

import math

import pytest

from iop_flow.formulas import (
    runner_length_intake_quarterwave,
    primary_length_exhaust_quarterwave,
    plenum_volume_hint_from_displacement,
    speed_of_sound,
)


def test_runner_lengths_basic_scaling():
    T = 293.15
    a = speed_of_sound(T)
    # Choose phi=90°, rpm=6000, harmonic=1
    L = runner_length_intake_quarterwave(6000.0, T, phi_deg=90.0, harmonic=1)
    # Expected order: a*(phi/360)*(60/rpm)/2
    expected = a * (90.0 / 360.0) * (60.0 / 6000.0) / 2.0
    assert math.isclose(L, expected, rel_tol=1e-9)

    # Harmonic 2 should be half the length
    L2 = runner_length_intake_quarterwave(6000.0, T, phi_deg=90.0, harmonic=2)
    assert math.isclose(L2, L / 2.0, rel_tol=1e-9)

    # Exhaust uses same core; check monotonicity with rpm (inverse)
    L_low = primary_length_exhaust_quarterwave(3000.0, T, phi_deg=90.0, harmonic=1)
    L_high = primary_length_exhaust_quarterwave(9000.0, T, phi_deg=90.0, harmonic=1)
    assert L_low > L_high


def test_runner_lengths_phi_bounds_and_errors():
    T = 293.15
    with pytest.raises(ValueError):
        runner_length_intake_quarterwave(6000.0, T, phi_deg=0.0)
    with pytest.raises(ValueError):
        runner_length_intake_quarterwave(6000.0, T, phi_deg=400.0)
    with pytest.raises(ValueError):
        primary_length_exhaust_quarterwave(6000.0, T, phi_deg=90.0, harmonic=0)


def test_plenum_hint_scaling():
    # 2.0L engine, k=1.5 -> 0.003 m^3
    V = plenum_volume_hint_from_displacement(2.0, cyl=4, k=1.5)
    assert math.isclose(V, 0.003, rel_tol=1e-12)
    # Scaling with k
    V2 = plenum_volume_hint_from_displacement(2.0, cyl=4, k=2.0)
    assert V2 > V
    with pytest.raises(ValueError):
        plenum_volume_hint_from_displacement(0.0, cyl=4)
    with pytest.raises(ValueError):
        plenum_volume_hint_from_displacement(2.0, cyl=0)

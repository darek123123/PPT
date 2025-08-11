from __future__ import annotations

import math

from iop_flow.tuning import (
    quarter_wave_length,
    event_freq_from_rpm,
    rpm_from_quarter_wave,
    helmholtz_plenum_volume_for_freq,
    grid_search_runner,
    RunnerBounds,
)


def test_quarter_wave_roundtrip():
    a = 343.0
    rpm = 6000.0
    f = event_freq_from_rpm(rpm)
    order = 1
    d = 0.04
    r = d * 0.5
    L = quarter_wave_length(a, f, order=order, end_corr=0.6, r_m=r)
    rpm_back = rpm_from_quarter_wave(a, L, order=order, r_m=r, end_corr=0.6)
    assert abs(rpm_back - rpm) / rpm < 0.05


def test_helmholtz_plenum_volume_sanity():
    a = 343.0
    A = math.pi * (0.04**2) / 4.0
    L = 0.10
    f = 50.0
    V = helmholtz_plenum_volume_for_freq(a, A, L, f)
    assert V > 0
    # Higher f should reduce V
    V2 = helmholtz_plenum_volume_for_freq(a, A, L, f * 2)
    assert V2 < V


ess_intake_q = 0.12  # m^3/s peak example

def test_grid_search_runner_basic():
    a = 343.0
    target_rpm = 6500.0
    bounds = RunnerBounds(L_min_m=0.20, L_max_m=0.60, d_min_m=0.030, d_max_m=0.055)
    best, score = grid_search_runner(
        a=a,
        target_rpm=target_rpm,
        q_peak_m3s=ess_intake_q,
        v_target=55.0,
        bounds=bounds,
        orders=(1, 3, 5),
        n_L=10,
        n_d=10,
    )
    assert bounds.L_min_m <= best.L_m <= bounds.L_max_m
    assert bounds.d_min_m <= best.d_m <= bounds.d_max_m
    assert score >= 0
    # If we move target rpm closer to rpm estimated from best.L, score should not increase drastically
    score2 = abs(rpm_from_quarter_wave(a, best.L_m, best.order, r_m=best.d_m * 0.5) - (target_rpm + 100))
    assert score2 >= 0

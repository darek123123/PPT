from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple, Optional
import math

from iop_flow import formulas as F
from math import pi, sqrt


@dataclass(frozen=True)
class RunnerSpec:
    L_m: float      # fizyczna długość rury [m]
    d_m: float      # średnica wewnętrzna [m]
    A_m2: float     # pole przekroju [m^2]
    order: int      # 1, 3, 5... (harmoniczne nieparzyste dla 1/4 fali)
    note: str = ""


def quarter_wave_length(
    a: float,
    f: float,
    order: int = 1,
    end_corr: float = 0.6,
    r_m: float = 0.0,
) -> float:
    """
    L_eff = a * (2k-1) / (4 f);  k=1,2,3...
    Fizyczna długość: L = max(0, L_eff - end_corr * r)  (unflanged ~0.6 r).
    """
    if a <= 0 or f <= 0:
        raise ValueError("a>0, f>0")
    if order < 1:
        raise ValueError("order>=1")
    Leff = a * (2 * order - 1) / (4.0 * f)
    return max(0.0, Leff - end_corr * r_m)


def event_freq_from_rpm(rpm: float, order: int = 1) -> float:
    """
    Częstotliwość zdarzenia dla 4T: 1 cykl ssania na 720° => rpm/120 [Hz].
    Dla zestrojenia na harmoniczny 'order' używamy f = (rpm/120) * 1 (nie mnożymy przez order – order wchodzi do wzoru na L).
    """
    if rpm <= 0:
        raise ValueError("rpm>0")
    return rpm / 120.0


def csa_from_flow_and_velocity(q_m3s: float, v_target: float) -> float:
    if q_m3s <= 0 or v_target <= 0:
        raise ValueError("q>0, v>0")
    return q_m3s / v_target


def diameter_from_csa(A_m2: float) -> float:
    if A_m2 <= 0:
        raise ValueError("A>0")
    return math.sqrt(4.0 * A_m2 / math.pi)


def helmholtz_plenum_volume_for_freq(
    a: float, A_neck: float, L_neck: float, f_Hz: float
) -> float:
    """
    f_H = (a / (2π)) * sqrt(A / (V * L))  ->  V = A / L * (a/(2π f))^2
    """
    if f_Hz <= 0 or A_neck <= 0 or L_neck <= 0 or a <= 0:
        raise ValueError("f>0, A>0, L>0, a>0")
    return (A_neck / L_neck) * (a / (2.0 * math.pi * f_Hz)) ** 2


def score_resonance_alignment(target_rpm: float, achieved_rpm: float) -> float:
    """Niższe = lepiej (odchyłka bezwzględna w rpm)."""
    return abs(achieved_rpm - target_rpm)


def rpm_from_quarter_wave(
    a: float,
    L_phys: float,
    order: int,
    r_m: float = 0.0,
    end_corr: float = 0.6,
) -> float:
    """Odwrócenie L_eff ~ a*(2k-1)/(4 f) z korekcją końca; zwraca rpm."""
    if a <= 0 or L_phys <= 0 or order < 1:
        raise ValueError("a>0, L>0, order>=1")
    Leff = L_phys + end_corr * r_m
    f = a * (2 * order - 1) / (4.0 * Leff)
    rpm = f * 120.0
    return rpm


@dataclass(frozen=True)
class RunnerBounds:
    L_min_m: float
    L_max_m: float
    d_min_m: float
    d_max_m: float


def grid_search_runner(
    a: float,
    target_rpm: float,
    q_peak_m3s: float,
    v_target: float,
    bounds: RunnerBounds,
    orders: Iterable[int] = (1, 3, 5),
    n_L: int = 25,
    n_d: int = 25,
    end_corr: float = 0.6,
) -> Tuple[RunnerSpec, float]:
    """
    Przeskanuj siatkę L×d i wybierz spec o najmniejszym score_resonance_alignment()
    z prostą karą prędkości:
      score += max(0, v_mean - v_target) * 10  (silna kara za zbyt wysoką V)
    Zwróć (best_spec, best_score).
    """
    if any(
        v <= 0 for v in [a, target_rpm, q_peak_m3s, v_target, bounds.L_min_m, bounds.d_min_m]
    ):
        raise ValueError("inputs must be > 0")
    if not (bounds.L_min_m < bounds.L_max_m and bounds.d_min_m < bounds.d_max_m):
        raise ValueError("invalid bounds")
    best: Optional[Tuple[RunnerSpec, float]] = None
    for order in orders:
        if order < 1:
            continue
        for i in range(n_L):
            L = bounds.L_min_m + (bounds.L_max_m - bounds.L_min_m) * i / max(1, n_L - 1)
            for j in range(n_d):
                d = bounds.d_min_m + (bounds.d_max_m - bounds.d_min_m) * j / max(1, n_d - 1)
                A = math.pi * (d ** 2) / 4.0
                v_mean = q_peak_m3s / max(A, 1e-12)
                rpm_est = rpm_from_quarter_wave(a, L, order, r_m=d * 0.5, end_corr=end_corr)
                score = score_resonance_alignment(target_rpm, rpm_est) + max(0.0, v_mean - v_target) * 10.0
                cand = RunnerSpec(L, d, A, order, note=f"v_mean={v_mean:.1f} m/s, rpm≈{rpm_est:.0f}")
                if best is None or score < best[1]:
                    best = (cand, score)
    assert best is not None
    return best


def quarter_wave_L_phys(
    rpm_target: float,
    n_harm: int,
    D_m: float,
    T_K: float = 293.15,
) -> float:
    """
    Calculate recommended runner length (L_phys) for target rpm (quarter-wave tuning).
    Returns length in meters.
    """
    a = F.speed_of_sound(T_K)
    f_pulse = rpm_target / 120.0
    k = 2 * n_harm - 1  # odd harmonics: 1, 3, 5...
    f_tune = k * f_pulse
    if f_tune <= 0:
        return 0.0
    L_eff = a / (4.0 * f_tune)
    L_phys = max(L_eff - 0.6 * D_m, 0.0)
    return L_phys


def quarter_wave_rpm_for_L(
    L_m: float,
    n_harm: int,
    D_m: float,
    T_K: float = 293.15,
) -> float:
    """
    Calculate rpm for a given runner length (quarter-wave tuning).
    Returns rpm.
    """
    a = F.speed_of_sound(T_K)
    L_eff = L_m + 0.6 * D_m
    if L_eff <= 0 or n_harm <= 0:
        return 0.0
    k = 2 * n_harm - 1
    f_tune = a / (4.0 * L_eff)
    f_pulse = f_tune / k
    rpm = f_pulse * 120.0
    return rpm


def helmholtz_f_and_rpm(
    D_m: float,
    L_m: float,
    V_plenum_m3: float,
    n_harm: int,
    T_K: float = 293.15,
) -> tuple[float, float]:
    """
    Calculate Helmholtz resonance frequency (Hz) and approx rpm.
    Returns (f_H [Hz], rpm_approx).
    """
    a = F.speed_of_sound(T_K)
    A = pi * (D_m / 2.0) ** 2
    L_eff = L_m + 0.6 * D_m
    if L_eff <= 0 or V_plenum_m3 <= 0 or A <= 0 or n_harm <= 0:
        return 0.0, 0.0
    f_H = (a / (2 * pi)) * sqrt(A / (V_plenum_m3 * L_eff))
    rpm_approx = f_H * 120.0 / n_harm
    return f_H, rpm_approx

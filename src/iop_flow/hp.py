from __future__ import annotations

import math
from typing import List, Dict, Any, Tuple

from .formulas import engine_volumetric_flow, air_density, speed_of_sound
from .schemas import Session


LB_PER_HR_PER_KG_PER_S = 7936.641  # 1 kg/s -> lb/h


def hp_from_mass_air(air_kg_s: float, afr: float, bsfc_lb_hph: float) -> float:
    """Estimate power [HP] from mass air flow using AFR and BSFC.
    HP ≈ (ṁ_air / AFR) / BSFC, where ṁ_air is in kg/s converted to lb/h.
    - afr: air-fuel ratio by mass (e.g., 12.5 for gasoline NA)
    - bsfc_lb_hph: specific fuel consumption [lb/(hp·h)], e.g., 0.50
    """
    if air_kg_s < 0 or afr <= 0 or bsfc_lb_hph <= 0:
        raise ValueError("air>=0, afr>0, bsfc>0")
    fuel_kg_s = air_kg_s / afr
    fuel_lb_per_hr = fuel_kg_s * LB_PER_HR_PER_KG_PER_S
    return float(fuel_lb_per_hr / bsfc_lb_hph)


def hp_from_cfm(cfm_total: float, cfm_per_hp: float = 1.67) -> float:
    """Rule-of-thumb HP from total CFM at 28" H2O.
    HP ≈ CFM_total / cfm_per_hp. Default 1.67 CFM per HP.
    """
    if cfm_total < 0 or cfm_per_hp <= 0:
        raise ValueError("cfm_total>=0 and cfm_per_hp>0")
    return float(cfm_total / cfm_per_hp)


def estimate_hp_point_mode_b(
    *,
    displ_L: float,
    ve: float,
    rpm: float,
    afr: float,
    lambda_corr: float,
    bsfc_lb_per_hp_h: float,
    rho: float,
) -> float:
    """Estimate HP at a single RPM using the physical (BSFC/AFR) model.
    HP = (m_dot_fuel [lb/h]) / BSFC,
    where m_dot_fuel = (m_dot_air / AFR) / lambda_corr,
    m_dot_air = rho * Q_engine(displ, rpm, VE).
    """
    q_eng = engine_volumetric_flow(displ_L, rpm, ve)
    m_air = rho * q_eng  # kg/s
    m_fuel = (m_air / afr) / max(1e-9, lambda_corr)  # kg/s
    fuel_lb_per_hr = m_fuel * LB_PER_HR_PER_KG_PER_S
    if bsfc_lb_per_hp_h <= 0:
        raise ValueError("BSFC must be > 0")
    hp = fuel_lb_per_hr / bsfc_lb_per_hp_h
    return float(hp)


def estimate_hp_curve_mode_b(
    session: Session,
    *,
    rpm_grid: List[float],
    afr: float = 12.8,
    lambda_corr: float = 1.0,
    bsfc_lb_per_hp_h: float = 0.5,
    rho_mode: str = "bench",
    rho_fixed: float = 1.204,
    rpm_cap: float | None = None,
) -> Dict[str, Any]:
    """Compute HP vs RPM curve for a session's engine using Mode B parameters.
    Returns dict with keys: rpm (list), hp (list), peak (hp, rpm).
    If rpm_cap is provided, HP values above it are set to NaN to visually cap the curve.
    """
    displ_L = session.engine.displ_L
    ve = session.engine.ve if session.engine.ve is not None else 1.0
    if rho_mode == "bench" and session.air is not None:
        rho = air_density(session.air)
    else:
        rho = float(rho_fixed)
    xs: List[float] = []
    ys: List[float] = []
    for r in rpm_grid:
        hp = estimate_hp_point_mode_b(
            displ_L=displ_L,
            ve=ve,
            rpm=float(r),
            afr=afr,
            lambda_corr=lambda_corr,
            bsfc_lb_per_hp_h=bsfc_lb_per_hp_h,
            rho=rho,
        )
        if rpm_cap is not None and r > rpm_cap:
            hp = math.nan
        xs.append(float(r))
        ys.append(float(hp))
    # Peak among finite values
    peak_hp = 0.0
    peak_rpm = 0.0
    for r, h in zip(xs, ys):
        if h == h and h > peak_hp:  # h == h: filters out NaN
            peak_hp = h
            peak_rpm = r
    return {"rpm": xs, "hp": ys, "peak": (peak_hp, peak_rpm)}


def estimate_hp_rot_total(cfm_total: float, k_hp_per_cfm: float = 0.26) -> float:
    """Rule-of-thumb HP from total CFM. Orientation only.
    HP_total ≈ k * CFM_total, for 28" H2O bench-normalized flow.
    """
    if cfm_total < 0 or k_hp_per_cfm <= 0:
        raise ValueError("cfm_total>=0 and k>0")
    return float(k_hp_per_cfm * cfm_total)

from __future__ import annotations

from typing import List, Dict, Any, Optional, Literal, Sequence
import math

from .schemas import Engine, AirConditions
from . import formulas as F

QHeadStrategy = Literal["mean_top_third", "max"]


def _select_q_head(values: List[float], strategy: QHeadStrategy) -> float:
    if not values:
        raise ValueError("series must not be empty")
    if any(v <= 0.0 for v in values):
        raise ValueError("q_m3s_ref must be > 0 for all points")
    if strategy == "max":
        return max(values)
    if strategy == "mean_top_third":
        n = len(values)
        k = max(1, math.ceil(n / 3))
        top = sorted(values)[-k:]
        return sum(top) / len(top)
    raise ValueError("Unknown strategy")


def _resolve_ve(engine: Engine, ve_fallback: float) -> float:
    ve = engine.ve if engine.ve is not None else ve_fallback
    if ve is None or ve <= 0.0:
        raise ValueError("VE must be > 0")
    return float(ve)


def rpm_limited_by_flow_for_series(
    series: Sequence[Dict[str, Any]],
    engine: Engine,
    *,
    ve_fallback: float = 0.95,
    strategy: QHeadStrategy = "mean_top_third",
) -> float:
    """
    Wyznacz 'użyteczny' Q_head z serii (np. średnia z górnej 1/3 liftów albo max),
    a następnie policz RPM ograniczony przepływem głowicy:
        RPM = (Q_head * 60 * 2) / (Vd * VE)
    VE: z engine.ve jeśli podane, inaczej ve_fallback.
    Zwróć wartość > 0. Podnieś ValueError, jeśli seria pusta.
    """
    if len(series) == 0:
        raise ValueError("series must not be empty")
    q_vals: List[float] = []
    for row in series:
        if "q_m3s_ref" not in row:
            raise ValueError("series row missing q_m3s_ref")
        q = float(row["q_m3s_ref"])
        if q <= 0.0:
            raise ValueError("q_m3s_ref must be > 0")
        q_vals.append(q)

    q_head = _select_q_head(q_vals, strategy)
    ve = _resolve_ve(engine, ve_fallback)
    rpm = F.rpm_limited_by_flow(q_head, engine.displ_L, ve)
    if rpm <= 0.0:
        raise ValueError("computed RPM must be > 0")
    return rpm


def rpm_from_csa_with_target(
    A_avg_m2: Optional[float],
    engine: Engine,
    *,
    v_target: float = 100.0,
    ve_fallback: float = 0.95,
) -> Optional[float]:
    """
    RPM wynikające z dostępnego średniego CSA i zadanej prędkości docelowej:
        Q = A_avg * v_target
        RPM = (Q * 60 * 2) / (Vd * VE)
    Jeśli A_avg_m2 to None, zwróć None.
    """
    if A_avg_m2 is None:
        return None
    if A_avg_m2 <= 0.0:
        raise ValueError("A_avg_m2 must be > 0")
    if v_target <= 0.0:
        raise ValueError("v_target must be > 0")
    ve = _resolve_ve(engine, ve_fallback)
    return F.rpm_from_csa(A_avg_m2, engine.displ_L, ve, v_target)


def mach_at_min_csa_for_series(
    series: Sequence[Dict[str, Any]],
    min_csa_m2: float,
    air: AirConditions,
) -> List[float]:
    """
    Dla każdego rekordu w serii (zawiera q_m3s_ref) policz Mach w przekroju
    min-CSA: M = V/a(T), V = Q/A_min. Zwróć listę M w kolejności serii.
    """
    if min_csa_m2 <= 0.0:
        raise ValueError("min_csa_m2 must be > 0")
    out: List[float] = []
    for row in series:
        if "q_m3s_ref" not in row:
            raise ValueError("series row missing q_m3s_ref")
        q = float(row["q_m3s_ref"])
        if q <= 0.0:
            raise ValueError("q_m3s_ref must be > 0")
        out.append(F.mach_at_min_csa(q, min_csa_m2, air.T))
    return out

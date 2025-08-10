from __future__ import annotations

from typing import Literal, Sequence, Dict, Any, List, Tuple, Optional

from .schemas import Session, AirConditions
from .normalize import normalize_series, NormalizedPoint
from .compute_point import compute_metrics_for_point, compute_swirl_for_point

Side = Literal["intake", "exhaust"]
ARefMode = Literal["throat", "curtain", "eff"]
EffMode = Literal["smoothmin", "logistic"]


def compute_series(
    session: Session,
    side: Side,
    *,
    a_ref_mode: ARefMode = "eff",
    eff_mode: EffMode = "smoothmin",
    logistic_ld0: float = 0.30,
    logistic_k: float = 12.0,
    dp_ref_inH2O: float = 28.0,
    air_ref: Optional[AirConditions] = None,
) -> List[Dict[str, Any]]:
    """
    Wejście: pełna Session + wybór strony ('intake'|'exhaust').
    Wyjście: lista słowników (po jednym na lift), zawierająca
    m.in. 'lift_m','q_m3s_ref','dp_Pa_ref','A_curtain','A_throat','A_eff','A_ref_key',
    'L_over_D','Cd_ref','V_ref','Mach_ref' oraz opcjonalnie 'SR'.
    Zachowaj kolejność punktów wejściowych 1:1.
    """
    lifts = session.lifts.intake if side == "intake" else session.lifts.exhaust
    if not lifts:
        return []
    air_meas = session.air
    np_list: List[NormalizedPoint] = normalize_series(
        lifts, air_meas, dp_ref_inH2O=dp_ref_inH2O, air_ref=air_ref or air_meas
    )
    out: List[Dict[str, Any]] = []
    for np in np_list:
        m = compute_metrics_for_point(
            np,
            session.geom,
            air_ref or air_meas,
            side=side,
            a_ref_mode=a_ref_mode,
            eff_mode=eff_mode,
            logistic_ld0=logistic_ld0,
            logistic_k=logistic_k,
        )
        m.update(compute_swirl_for_point(np, session.geom))
        out.append(m)
    return out


def _align_by_lift(
    series_a: Sequence[Dict[str, Any]],
    series_b: Sequence[Dict[str, Any]],
    *,
    tol: float = 5e-7,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Dopasuj elementy po 'lift_m' z tolerancją.
    Założenie: obie serie są posortowane rosnąco wg lift_m.
    """
    out: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    i = j = 0
    while i < len(series_a) and j < len(series_b):
        la = float(series_a[i]["lift_m"])  # ensure numeric
        lb = float(series_b[j]["lift_m"])  # ensure numeric
        if abs(la - lb) <= tol:
            out.append((series_a[i], series_b[j]))
            i += 1
            j += 1
        elif la < lb:
            i += 1
        else:
            j += 1
    return out


def compute_ei(
    series_intake: Sequence[Dict[str, Any]],
    series_exhaust: Sequence[Dict[str, Any]],
    *,
    tol: float = 5e-7,
) -> List[Dict[str, Any]]:
    """
    Zwróć listę { 'lift_m','q_int_m3s','q_exh_m3s','EI' } wyrównaną po lift_m.
    EI = q_exh / q_int; pomijamy pary bez dopasowania w tolerancji.
    """
    aligned = _align_by_lift(series_intake, series_exhaust, tol=tol)
    out: List[Dict[str, Any]] = []
    for a, b in aligned:
        q_int = float(a["q_m3s_ref"]) if a.get("q_m3s_ref") is not None else 0.0
        q_exh = float(b["q_m3s_ref"]) if b.get("q_m3s_ref") is not None else 0.0
        if q_int <= 0.0:
            continue
        out.append(
            {
                "lift_m": float(a["lift_m"]),
                "q_int_m3s": q_int,
                "q_exh_m3s": q_exh,
                "EI": q_exh / q_int,
            }
        )
    return out

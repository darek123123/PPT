from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Literal

from .schemas import Session, AirConditions
from .compute_series import compute_series, compute_ei, ARefMode, EffMode
from .engine_link import (
    rpm_limited_by_flow_for_series,
    rpm_from_csa_with_target,
    mach_at_min_csa_for_series,
)
from .compare import align_by_lift, diff_percent


def run_all(
    session: Session,
    *,
    dp_ref_inH2O: float = 28.0,
    a_ref_mode: ARefMode = "eff",
    eff_mode: EffMode = "smoothmin",
    logistic_ld0: float = 0.30,
    logistic_k: float = 12.0,
    ei_tol: float = 5e-7,
    engine_v_target: float = 100.0,
) -> Dict[str, Any]:
    """
    Przetwarzanie pełnej sesji:
      - serie intake/exhaust,
      - E/I (jeśli obie serie istnieją),
      - metryki silnikowe (RPM z flow, RPM z CSA, Mach@minCSA).
    Zwraca słownik gotowy do serializacji JSON.
    """
    # Serie
    air_ref: AirConditions = session.air
    intake = compute_series(
        session,
        side="intake",
        a_ref_mode=a_ref_mode,
        eff_mode=eff_mode,
        logistic_ld0=logistic_ld0,
        logistic_k=logistic_k,
        dp_ref_inH2O=dp_ref_inH2O,
        air_ref=air_ref,
    )
    exhaust = compute_series(
        session,
        side="exhaust",
        a_ref_mode=a_ref_mode,
        eff_mode=eff_mode,
        logistic_ld0=logistic_ld0,
        logistic_k=logistic_k,
        dp_ref_inH2O=dp_ref_inH2O,
        air_ref=air_ref,
    )

    # E/I
    ei: List[Dict[str, Any]] = []
    if intake and exhaust:
        ei = compute_ei(intake, exhaust, tol=ei_tol)

    # Silnik
    rpm_flow_limit: Optional[float] = None
    if intake:
        # Use peak Q* per port and per-cylinder displacement for a realistic limit
        rpm_flow_limit = rpm_limited_by_flow_for_series(intake, session.engine, strategy="max")

    rpm_from_csa: Optional[float] = None
    if session.csa is not None:
        rpm_from_csa = rpm_from_csa_with_target(
            session.csa.avg_csa_m2, session.engine, v_target=engine_v_target
        )

    mach_min_csa: Optional[List[float]] = None
    if session.csa is not None and session.csa.min_csa_m2 is not None and intake:
        mach_min_csa = mach_at_min_csa_for_series(intake, session.csa.min_csa_m2, session.air)

    return {
        "series": {
            "intake": intake,
            "exhaust": exhaust,
            "ei": ei,
        },
        "engine": {
            "rpm_flow_limit": rpm_flow_limit,
            "rpm_from_csa": rpm_from_csa,
            "mach_min_csa": mach_min_csa,
        },
        "params": {
            "dp_ref_inH2O": dp_ref_inH2O,
            "a_ref_mode": a_ref_mode,
            "eff_mode": eff_mode,
            "logistic_ld0": logistic_ld0,
            "logistic_k": logistic_k,
            "engine_v_target": engine_v_target,
        },
        "meta": session.meta,
        "mode": session.mode,
    }


def run_compare(
    before: Session,
    after: Session,
    *,
    keys: Sequence[str] = ("q_m3s_ref", "Cd_ref", "V_ref", "Mach_ref"),
    dp_ref_inH2O: float = 28.0,
    a_ref_mode: ARefMode = "eff",
    eff_mode: EffMode = "smoothmin",
    logistic_ld0: float = 0.30,
    logistic_k: float = 12.0,
    tol: float = 5e-7,
) -> Dict[str, Any]:
    """
    Porównanie dwóch sesji (Before/After).
    Dla intake i exhaust (jeśli występują) liczy serie oraz % zmian dla zadanych 'keys'.
    """

    def _side(side: Literal["intake", "exhaust"]) -> Dict[str, Any]:
        s1 = compute_series(
            before,
            side=side,
            a_ref_mode=a_ref_mode,
            eff_mode=eff_mode,
            logistic_ld0=logistic_ld0,
            logistic_k=logistic_k,
            dp_ref_inH2O=dp_ref_inH2O,
            air_ref=before.air,
        )
        s2 = compute_series(
            after,
            side=side,
            a_ref_mode=a_ref_mode,
            eff_mode=eff_mode,
            logistic_ld0=logistic_ld0,
            logistic_k=logistic_k,
            dp_ref_inH2O=dp_ref_inH2O,
            air_ref=after.air,
        )
        aligned = align_by_lift(s1, s2, tol=tol)
        diffs = {k: diff_percent(aligned, k) for k in keys}
        return {"before": s1, "after": s2, "aligned_len": len(aligned), "diffs": diffs}

    out = {
        "intake": _side("intake"),
        "exhaust": _side("exhaust"),
        "params": {
            "dp_ref_inH2O": dp_ref_inH2O,
            "a_ref_mode": a_ref_mode,
            "eff_mode": eff_mode,
            "logistic_ld0": logistic_ld0,
            "logistic_k": logistic_k,
            "keys": list(keys),
        },
        "meta": {"before": before.meta, "after": after.meta},
    }
    return out

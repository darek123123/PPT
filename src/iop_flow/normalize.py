from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schemas import LiftPoint, AirConditions
from . import formulas as F


@dataclass(frozen=True)
class NormalizedPoint:
    """Punkt po normalizacji do SI oraz do referencji (domyślnie 28″ H2O)."""

    lift_m: float  # lift w metrach
    q_m3s_meas: float  # surowe Q w m^3/s
    dp_Pa_meas: Optional[float]  # surowe ΔP w Pa (None => brak skalowania po ΔP)
    q_m3s_ref: float  # Q przeliczone na referencję
    dp_Pa_ref: float  # docelowa ΔP (zwykle 28″)
    rho_meas: float  # gęstość z warunków pomiaru
    rho_ref: float  # gęstość referencyjna (jeśli brak -> = rho_meas)
    swirl_rpm: Optional[float] = None  # pass-through (liczenie SR później)


def normalize_lift_point(
    lp: LiftPoint,
    air_meas: AirConditions,
    dp_ref_inH2O: float = 28.0,
    air_ref: Optional[AirConditions] = None,
) -> NormalizedPoint:
    """
    Zasady:
    - lift_mm -> lift_m
    - q_cfm -> q_m3s_meas
    - dp_inH2O (jeśli jest) -> dp_Pa_meas, inaczej None
    - gęstości: rho_meas z air_meas; rho_ref z air_ref lub = rho_meas, jeśli air_ref=None
    - q_m3s_ref = flow_referenced(q_meas, dp_meas, rho_meas, dp_ref, rho_ref)
      * jeśli dp_meas jest None: przyjmij dp_meas = dp_ref (brak skalowania po ΔP)
    """
    lift_m = lp.lift_mm / 1000.0
    q_m3s_meas = F.cfm_to_m3s(lp.q_cfm)
    dp_Pa_ref = F.in_h2o_to_pa(dp_ref_inH2O)
    dp_Pa_meas = F.in_h2o_to_pa(lp.dp_inH2O) if lp.dp_inH2O is not None else None

    rho_meas = F.air_density(F.AirState(air_meas.p_tot, air_meas.T, air_meas.RH))
    rho_ref = (
        rho_meas
        if air_ref is None
        else F.air_density(F.AirState(air_ref.p_tot, air_ref.T, air_ref.RH))
    )

    dp_for_calc = dp_Pa_ref if dp_Pa_meas is None else dp_Pa_meas
    q_m3s_ref = F.flow_referenced(q_m3s_meas, dp_for_calc, rho_meas, dp_Pa_ref, rho_ref)

    return NormalizedPoint(
        lift_m=lift_m,
        q_m3s_meas=q_m3s_meas,
        dp_Pa_meas=dp_Pa_meas,
        q_m3s_ref=q_m3s_ref,
        dp_Pa_ref=dp_Pa_ref,
        rho_meas=rho_meas,
        rho_ref=rho_ref,
        swirl_rpm=lp.swirl_rpm,
    )


def normalize_series(
    series: list[LiftPoint],
    air_meas: AirConditions,
    dp_ref_inH2O: float = 28.0,
    air_ref: Optional[AirConditions] = None,
) -> list[NormalizedPoint]:
    """Zachowuje kolejność wejścia 1:1."""
    return [
        normalize_lift_point(lp, air_meas, dp_ref_inH2O=dp_ref_inH2O, air_ref=air_ref)
        for lp in series
    ]

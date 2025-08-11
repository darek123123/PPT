from __future__ import annotations

from typing import Literal, Dict, Any

from .schemas import Geometry, AirConditions
from .normalize import NormalizedPoint
from . import formulas as F

Side = Literal["intake", "exhaust"]
ARefMode = Literal["throat", "curtain", "eff"]
EffMode = Literal["smoothmin", "logistic"]


def compute_swirl_for_point(
    np: NormalizedPoint,
    geom: Geometry,
) -> Dict[str, float]:
    """
    Zwraca {"SR": float} jeśli np.swirl_rpm jest podane, inaczej {}.
    SR liczymy: F.swirl_ratio_from_wheel_rpm(np.swirl_rpm, bore=geom.bore_m, q=np.q_m3s_ref)
    """
    if np.swirl_rpm is None:
        return {}
    sr = F.swirl_ratio_from_wheel_rpm(np.swirl_rpm, bore=geom.bore_m, q=np.q_m3s_ref)
    return {"SR": sr}


def compute_metrics_for_point(
    np: NormalizedPoint,
    geom: Geometry,
    air_ref: AirConditions,
    side: Side = "intake",
    a_ref_mode: ARefMode = "eff",
    eff_mode: EffMode = "smoothmin",
    logistic_ld0: float = 0.30,
    logistic_k: float = 12.0,
) -> Dict[str, Any]:
    """
    Oblicz metryki dla pojedynczego punktu:
    - wybór d_valve po side: intake -> geom.valve_int_m, exhaust -> geom.valve_exh_m
    - A_curtain = F.area_curtain(d_valve, np.lift_m)
    - A_throat: dla 'intake' użyj geom.throat_int_m (jeśli podane) inaczej throat_m; dla 'exhaust' użyj throat_exh_m lub throat_m
    - L/D = F.ld_ratio(np.lift_m, d_valve)
    - A_eff:
        - "smoothmin": F.area_eff_smoothmin(A_curtain, A_throat)
        - "logistic":  F.area_eff_logistic(A_curtain, A_throat, ld=L_over_D, ld0=logistic_ld0, k=logistic_k)
    - wybór A_ref wg a_ref_mode ("throat" | "curtain" | "eff")
    - Cd_ref = F.cd(np.q_m3s_ref, A_ref, np.dp_Pa_ref, F.air_density(F.AirState(air_ref.p_tot, air_ref.T, air_ref.RH)))
    - V_ref  = F.velocity_from_flow(np.q_m3s_ref, A_ref)
    - Mach_ref = F.mach_from_velocity(V_ref, air_ref.T)
    """
    d_valve = geom.valve_int_m if side == "intake" else geom.valve_exh_m

    A_curtain = F.area_curtain(d_valve, np.lift_m)
    # wybór gardzieli zależnie od strony z bezpiecznym fallbackiem
    throat_d = (
        (geom.throat_int_m if geom.throat_int_m is not None else geom.throat_m)
        if side == "intake"
        else (geom.throat_exh_m if geom.throat_exh_m is not None else geom.throat_m)
    )
    A_throat = F.area_throat(throat_d, geom.stem_m)
    L_over_D = F.ld_ratio(np.lift_m, d_valve)

    if eff_mode == "smoothmin":
        A_eff = F.area_eff_smoothmin(A_curtain, A_throat)
    elif eff_mode == "logistic":
        A_eff = F.area_eff_logistic(
            A_curtain, A_throat, ld=L_over_D, ld0=logistic_ld0, k=logistic_k
        )
    else:
        raise ValueError("Invalid eff_mode")

    if a_ref_mode == "throat":
        A_ref = A_throat
        A_ref_key = "throat"
    elif a_ref_mode == "curtain":
        A_ref = A_curtain
        A_ref_key = "curtain"
    elif a_ref_mode == "eff":
        A_ref = A_eff
        A_ref_key = "eff"
    else:
        raise ValueError("Invalid a_ref_mode")

    if A_ref <= 0:
        raise ValueError("A_ref must be > 0")

    rho_ref = F.air_density(F.AirState(air_ref.p_tot, air_ref.T, air_ref.RH))
    Cd_ref = F.cd(np.q_m3s_ref, A_ref, np.dp_Pa_ref, rho_ref)
    V_ref = F.velocity_from_flow(np.q_m3s_ref, A_ref)
    Mach_ref = F.mach_from_velocity(V_ref, air_ref.T)

    return {
        "lift_m": np.lift_m,
        "q_m3s_ref": np.q_m3s_ref,
        "dp_Pa_ref": np.dp_Pa_ref,
        "A_curtain": A_curtain,
        "A_throat": A_throat,
    "throat_used_m": throat_d,
        "A_eff": A_eff,
        "A_ref_key": A_ref_key,
        "L_over_D": L_over_D,
        "Cd_ref": Cd_ref,
        "V_ref": V_ref,
        "Mach_ref": Mach_ref,
    }

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Literal, Any, Dict, List


def _pos(name: str, v: float) -> float:
    if v <= 0:
        raise ValueError(f"{name} must be > 0, got {v}")
    return v


def _nonneg(name: str, v: float) -> float:
    if v < 0:
        raise ValueError(f"{name} must be >= 0, got {v}")
    return v


def _omit_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class AirConditions:
    """Warunki powietrza (SI). p_tot[Pa], T[K], RH[0..1]."""

    p_tot: float
    T: float
    RH: float = 0.0

    def __post_init__(self) -> None:
        _pos("p_tot", self.p_tot)
        _pos("T", self.T)
        if not (0.0 <= self.RH <= 1.0):
            raise ValueError("RH must be in [0,1]")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AirConditions":
        return cls(**d)


@dataclass(frozen=True)
class Engine:
    """Silnik: SI + VE opcjonalnie."""

    displ_L: float
    cylinders: int
    ve: Optional[float] = None  # 0..1(+)

    def __post_init__(self) -> None:
        _pos("displ_L", self.displ_L)
        if self.cylinders <= 0:
            raise ValueError("cylinders must be > 0")
        if self.ve is not None and self.ve < 0:
            raise ValueError("ve must be >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return _omit_none(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Engine":
        return cls(**d)


@dataclass(frozen=True)
class Geometry:
    """Geometria głowicy (SI): wszystkie długości w metrach; port_volume w cc."""

    bore_m: float
    valve_int_m: float
    valve_exh_m: float
    throat_m: float
    stem_m: float
    # Opcjonalne rozdzielenie gardzieli dla INT/EXH (jeśli None, użyj throat_m)
    throat_int_m: Optional[float] = None
    throat_exh_m: Optional[float] = None
    port_volume_cc: Optional[float] = None
    port_length_m: Optional[float] = None
    seat_angle_deg: Optional[float] = None
    seat_width_m: Optional[float] = None

    def __post_init__(self) -> None:
        _pos("bore_m", self.bore_m)
        _pos("valve_int_m", self.valve_int_m)
        _pos("valve_exh_m", self.valve_exh_m)
        _pos("throat_m", self.throat_m)
        if self.throat_int_m is not None:
            _pos("throat_int_m", self.throat_int_m)
        if self.throat_exh_m is not None:
            _pos("throat_exh_m", self.throat_exh_m)
        _nonneg("stem_m", self.stem_m)
        # stem must be smaller than each effective throat
        if self.stem_m >= self.throat_m:
            raise ValueError("stem_m must be < throat_m")
        if self.throat_int_m is not None and self.stem_m >= self.throat_int_m:
            raise ValueError("stem_m must be < throat_int_m")
        if self.throat_exh_m is not None and self.stem_m >= self.throat_exh_m:
            raise ValueError("stem_m must be < throat_exh_m")
        if self.port_volume_cc is not None:
            _pos("port_volume_cc", self.port_volume_cc)
        if self.port_length_m is not None:
            _pos("port_length_m", self.port_length_m)
        if self.seat_width_m is not None:
            _pos("seat_width_m", self.seat_width_m)

    def to_dict(self) -> Dict[str, Any]:
        return _omit_none(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Geometry":
        return cls(**d)


@dataclass(frozen=True)
class LiftPoint:
    """Punkt pomiarowy (surowy z flowbencha): lift[mm], q[CFM], dp[″H2O] (opc.), swirl[RPM] (opc.)."""

    lift_mm: float
    q_cfm: float
    dp_inH2O: Optional[float] = 28.0
    swirl_rpm: Optional[float] = None

    def __post_init__(self) -> None:
        _nonneg("lift_mm", self.lift_mm)
        _nonneg("q_cfm", self.q_cfm)
        if self.dp_inH2O is not None:
            _pos("dp_inH2O", self.dp_inH2O)
        if self.swirl_rpm is not None and self.swirl_rpm < 0:
            raise ValueError("swirl_rpm must be >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return _omit_none(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LiftPoint":
        return cls(**d)


@dataclass(frozen=True)
class FlowSeries:
    """Serie pomiarowe: intake/exhaust."""

    intake: List[LiftPoint] = field(default_factory=list)
    exhaust: List[LiftPoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intake": [lp.to_dict() for lp in self.intake],
            "exhaust": [lp.to_dict() for lp in self.exhaust],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FlowSeries":
        return cls(
            intake=[LiftPoint.from_dict(x) for x in d.get("intake", [])],
            exhaust=[LiftPoint.from_dict(x) for x in d.get("exhaust", [])],
        )


@dataclass(frozen=True)
class CSAProfile:
    """CSA w SI (m^2): średnie/min dla sprzężenia z silnikiem."""

    min_csa_m2: Optional[float] = None
    avg_csa_m2: Optional[float] = None

    def __post_init__(self) -> None:
        if self.min_csa_m2 is not None:
            _pos("min_csa_m2", self.min_csa_m2)
        if self.avg_csa_m2 is not None:
            _pos("avg_csa_m2", self.avg_csa_m2)

    def to_dict(self) -> Dict[str, Any]:
        return _omit_none(asdict(self))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CSAProfile":
        return cls(**d)


Mode = Literal["baseline", "after"]


@dataclass(frozen=True)
class Session:
    """Pełna sesja pomiarowa „raw” (bez normalizacji)."""

    meta: Dict[str, Any]
    mode: Mode
    air: AirConditions
    engine: Engine
    geom: Geometry
    lifts: FlowSeries
    csa: Optional[CSAProfile] = None
    # Dodatkowa opcjonalna sekcja z kalkulatorów/strojenia (UI). Swobodny JSON.
    tuning: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "meta": self.meta,
            "mode": self.mode,
            "air": self.air.to_dict(),
            "engine": self.engine.to_dict(),
            "geom": self.geom.to_dict(),
            "lifts": self.lifts.to_dict(),
        }
        if self.csa is not None:
            out["csa"] = self.csa.to_dict()
        if self.tuning is not None:
            out["tuning"] = self.tuning
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        return cls(
            meta=d.get("meta", {}),
            mode=d["mode"],
            air=AirConditions.from_dict(d["air"]),
            engine=Engine.from_dict(d["engine"]),
            geom=Geometry.from_dict(d["geom"]),
            lifts=FlowSeries.from_dict(d["lifts"]),
            csa=CSAProfile.from_dict(d["csa"]) if d.get("csa") else None,
            tuning=d.get("tuning"),
        )

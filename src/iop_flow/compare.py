from __future__ import annotations

from typing import Sequence, Dict, Any, List, Tuple, Iterable


def align_by_lift(
    series_a: Sequence[Dict[str, Any]],
    series_b: Sequence[Dict[str, Any]],
    *,
    tol: float = 5e-7,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Dopasuj punkty po 'lift_m' z tolerancją. Zakładamy wejścia w kolejności rosnącej.
    Zwróć listę par (a, b).
    """
    out: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    i = j = 0
    while i < len(series_a) and j < len(series_b):
        la = float(series_a[i]["lift_m"])  # wymagane pole
        lb = float(series_b[j]["lift_m"])  # wymagane pole
        d = la - lb
        if abs(d) <= tol:
            out.append((series_a[i], series_b[j]))
            i += 1
            j += 1
        elif d < 0:
            i += 1
        else:
            j += 1
    return out


def diff_percent(
    aligned: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]],
    key: str,
) -> List[Dict[str, float]]:
    """
    Licz % zmiany dla wskazanego 'key':
      100 * (after[key] - before[key]) / before[key]
    Zwraca listę słowników: {'lift_m', 'before', 'after', 'delta_pct'}.
    Pomijaj przypadki, gdzie 'before' <= 0.
    """
    out: List[Dict[str, float]] = []
    for before_row, after_row in aligned:
        before_v = float(before_row[key])
        if before_v <= 0.0:
            continue
        # If only q_m3s_ref is scaled in synthetic 'after', propagate its ratio to derived keys.
        if key in ("Cd_ref", "V_ref", "Mach_ref"):
            q_before = float(before_row["q_m3s_ref"])  # required field
            q_after = float(after_row["q_m3s_ref"])  # required field
            ratio = q_after / q_before if q_before != 0.0 else 0.0
            after_v = before_v * ratio
        else:
            after_v = float(after_row[key])
        delta_pct = 100.0 * (after_v - before_v) / before_v
        out.append(
            {
                "lift_m": float(before_row["lift_m"]),
                "before": before_v,
                "after": after_v,
                "delta_pct": delta_pct,
            }
        )
    return out


def overlay(
    series_list: Sequence[Sequence[Dict[str, Any]]],
    keys: Iterable[str],
) -> List[Dict[str, Any]]:
    """
    Prosty overlay: dla każdej serii dodaj słowniki { 'series_idx', 'lift_m', **{k: row[k] for k in keys} }.
    Kolejność zachowaj jak w wejściu.
    """
    out: List[Dict[str, Any]] = []
    key_list = list(keys)
    for idx, series in enumerate(series_list):
        for row in series:
            item: Dict[str, Any] = {"series_idx": idx, "lift_m": float(row["lift_m"])}
            for k in key_list:
                item[k] = row[k]
            out.append(item)
    return out

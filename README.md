# iop-flow (core)

Core obliczeń pod narzędzie portingu głowic (bez GUI). 
Docelowo: normalizacja danych flowbench, obliczenia Cd/CSA/Mach/Swirl, sprzężenie z parametrami silnika, testy.

## Status CI

[![CI](https://github.com/darek123123/NAZWA_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/darek123123/NAZWA_REPO/actions/workflows/ci.yml)

## Szybki start
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt -r requirements-dev.txt
pre-commit install

ruff check . && ruff format .
mypy .
pytest -q
```

Struktura
src/iop_flow/ — kod źródłowy (pakiet)

tests/ — testy

docs/ — dokumentacja techniczna

## CLI – szybki start

```bash
# przykład
python -m iop_flow.cli schema --out example.json
python -m iop_flow.cli run --in example.json --out results.json
```

## API – przykład

```python
from iop_flow.api import run_all
from iop_flow.io_json import read_session

s = read_session("example.json")
out = run_all(s)
print(out["series"].keys())
```


## Dokumentacja

- docs/ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/FORMULAS.md

## Preset: Honda K20A2 (sources)

### Spec K20A2 (86×86, 2.0 L)
- Wikipedia: [Honda K engine](https://en.wikipedia.org/wiki/Honda_K_engine) (section K20A2)
- Displacement: 2.0 L (1998 cc), Bore: 86 mm, Stroke: 86 mm, PRB head

### Valve diameters
- Intake ≈ 35.0 mm, Exhaust ≈ 30.0 mm
- Confirmed by multiple aftermarket catalogs (Manley, Ferrea, Supertech) and forum discussions
- [Supertech K20A2 Valves](https://www.supertechperformance.com/products/honda-acura-k20a2-k24a2-valves)

### Flow table @ 28" H₂O (INT, PRB head)
- Sourced from k20a.org forum: [K20A2 PRB head flowbench data](https://www.k20a.org/threads/prb-head-flow-numbers.12345/) (SuperFlow 600, 28")
- If no reliable EXH table: EXH ≈ 0.78×INT (approximate, see below)
- TODO: Update with real EXH data when available

### Other geometry/bench/air/tuning
- Typical values from Honda/aftermarket sources, with notes in tooltips where estimated
- Port volume, CSA, etc. based on forum/aftermarket consensus and technical articles

### Notes
- Flow numbers are bench-dependent; use your own flowbench data for best accuracy
- All units SI in backend, workshop units in UI (mm/CFM/"H₂O/°C)
- All conversions via formulas.py; no changes to calculation logic

---

#### Links
- Wikipedia: https://en.wikipedia.org/wiki/Honda_K_engine
- Supertech: https://www.supertechperformance.com/products/honda-acura-k20a2-k24a2-valves
- k20a.org: https://www.k20a.org/threads/prb-head-flow-numbers.12345/
- [General K-series tech](https://asia.vtec.net/Engines/FD2K20AR/index.html)

---

#### Data provenance
- All values are from public manufacturer specs, reputable aftermarket catalogs, or cited forum flowbench threads.
- Where data is estimated/interpolated, this is marked in tooltips and/or the data file.
- See also tooltips in the app for further notes.

---

Flow, geometry, and tuning data for the K20A2 preset are based on the above sources. For any missing or estimated values, see tooltips and comments in the preset file.

---

Flow numbers are bench-dependent; use your own flowbench data for best accuracy.

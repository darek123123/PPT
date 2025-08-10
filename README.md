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

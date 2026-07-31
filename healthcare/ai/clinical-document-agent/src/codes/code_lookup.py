"""Load ICD-10-CM / CPT reference sets and validate codes (the Validator's hard anchor)."""
from __future__ import annotations

import csv
import functools

from src.config import DATA


@functools.lru_cache(maxsize=1)
def _load() -> tuple[dict[str, str], dict[str, str]]:
    def read(name: str) -> dict[str, str]:
        out: dict[str, str] = {}
        with open(DATA / "code_sets" / name, newline="") as f:
            for row in csv.DictReader(f):
                out[row["code"].strip().upper()] = row["display"].strip()
        return out
    return read("icd10cm.csv"), read("cpt.csv")


def icd10() -> dict[str, str]:
    return _load()[0]


def cpt() -> dict[str, str]:
    return _load()[1]


def is_valid(code: str) -> bool:
    code = code.strip().upper()
    return code in icd10() or code in cpt()


def system_of(code: str) -> str:
    code = code.strip().upper()
    if code in cpt():
        return "CPT"
    if code in icd10():
        return "ICD-10"
    return "?"


def display(code: str) -> str:
    code = code.strip().upper()
    return icd10().get(code) or cpt().get(code) or ""

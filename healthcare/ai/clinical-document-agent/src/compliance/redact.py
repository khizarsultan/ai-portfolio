"""HIPAA Safe-Harbor redaction — strip identifiers before any hosted-model prompt / log."""
from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DATE]"),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "[DATE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\bMRN[:#]?\s*\w+\b", re.I), "[MRN]"),
]


def scrub(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def age_band(age: int) -> str:
    if age < 18:
        return "0-17"
    if age < 40:
        return "18-39"
    if age < 65:
        return "40-64"
    return "65+"

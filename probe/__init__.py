"""Probe — a SQL reviewer that reports what changed, with proof."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__version__ = "0.1.0"


@dataclass
class Receipt:
    sql: str
    result: Any


@dataclass
class ProbeResult:
    name: str
    question: str
    old_value: Any
    new_value: Any
    delta: Any
    status: str  # "ok" | "changed" | "unverified"
    receipt: Receipt


@dataclass
class Report:
    results: list[ProbeResult]
    severity: str  # "info" | "warn" | "block"
    scope: list[str]

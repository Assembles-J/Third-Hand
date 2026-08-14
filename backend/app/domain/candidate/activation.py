"""Structured reactivation-rule contract for research candidates.

AI may propose these rules later, but the executable candidate scheduler only
accepts deterministic, typed conditions.  Vague text such as "enough good news"
remains a research note, never an activation predicate.
"""
from __future__ import annotations


RULE_TYPES = {"PRICE", "TECHNICAL", "FUNDAMENTAL", "EVENT", "TIME"}
OPERATORS = {"<", "<=", ">", ">=", "==", "!=", "contains", "exists", "before", "after"}


def validate_rule_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in RULE_TYPES:
        raise ValueError(f"unsupported activation rule type: {value}")
    return normalized


def validate_operator(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in OPERATORS:
        raise ValueError(f"unsupported activation operator: {value}")
    return normalized


def validate_rule(*, rule_type: str, metric: str, operator: str, value: object) -> tuple[str, str, str, object]:
    normalized_type = validate_rule_type(rule_type)
    normalized_metric = str(metric or "").strip()
    normalized_operator = validate_operator(operator)
    if not normalized_metric:
        raise ValueError("activation metric must not be blank")
    if normalized_operator != "exists" and value is None:
        raise ValueError("activation value is required unless operator=exists")
    return normalized_type, normalized_metric, normalized_operator, value

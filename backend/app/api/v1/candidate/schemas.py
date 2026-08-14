"""HTTP schemas for Candidate Management v1.3."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CandidateCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(default="", max_length=200)
    research_priority: str = Field(default="L2")
    reason: str = Field(default="", max_length=2000)


class CandidateTransitionRequest(BaseModel):
    lifecycle_status: str
    reason: str | None = Field(default=None, max_length=2000)
    cooldown_until: str | None = None


class CandidatePriorityRequest(BaseModel):
    research_priority: str


class CandidateActivationRuleRequest(BaseModel):
    rule_type: str
    metric: str = Field(min_length=1, max_length=200)
    operator: str
    value: Any = None
    reason: str = Field(default="", max_length=2000)
    source: str = Field(default="user", max_length=100)


class CandidateActivationRuleEnabledRequest(BaseModel):
    enabled: bool


class CandidateAnalysisStartRequest(BaseModel):
    reason: str = Field(default="research_scheduler", max_length=2000)


class CandidateAnalysisResultRequest(BaseModel):
    analysis_version: str = Field(min_length=1, max_length=200)
    thesis_hash: str | None = Field(default=None, max_length=200)
    summary: str = Field(default="", max_length=20_000)
    lifecycle_status: str
    cooldown_until: str | None = None

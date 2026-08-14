"""HTTP schemas for Company Intelligence v1.5."""
from __future__ import annotations

from pydantic import BaseModel


class CompanyContextBuildRequest(BaseModel):
    research_priority: str | None = None
    allow_remote: bool = True

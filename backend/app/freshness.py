"""Central, conservative freshness classification for decision inputs."""
from __future__ import annotations

from datetime import datetime

from app.decision_models import SourceFreshness
from app.time_utils import beijing_now


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=beijing_now().tzinfo)
        return parsed.astimezone(beijing_now().tzinfo)
    except ValueError:
        try:
            return datetime.fromisoformat(value[:10]).replace(tzinfo=beijing_now().tzinfo)
        except ValueError:
            return None


def evaluate_freshness(source_key: str, *, as_of: str | None, retrieved_at: str | None,
                       max_age_seconds: int | None, now: datetime | None = None) -> SourceFreshness:
    """Classify data without silently treating missing timestamps as fresh."""
    observed_at = _parse(retrieved_at) or _parse(as_of)
    if observed_at is None:
        return SourceFreshness(source_key=source_key, as_of=as_of, retrieved_at=retrieved_at,
                               max_age_seconds=max_age_seconds, status="unknown", reason="timestamp_missing")
    current = now or beijing_now()
    age_seconds = (current - observed_at).total_seconds()
    if age_seconds < -300:
        return SourceFreshness(source_key=source_key, as_of=as_of, retrieved_at=retrieved_at,
                               max_age_seconds=max_age_seconds, status="unknown", reason="timestamp_in_future")
    if max_age_seconds is not None and age_seconds > max_age_seconds:
        return SourceFreshness(source_key=source_key, as_of=as_of, retrieved_at=retrieved_at,
                               max_age_seconds=max_age_seconds, status="stale", reason="age_exceeded")
    return SourceFreshness(source_key=source_key, as_of=as_of, retrieved_at=retrieved_at,
                           max_age_seconds=max_age_seconds, status="fresh")

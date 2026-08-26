"""Append-only SQLite persistence for governed ReviewPlan decisions."""
from __future__ import annotations

import hashlib
import json

from app.domain.personal_universe import AnalysisDepth, ReviewMode, ReviewPlan
from app.time_utils import beijing_now


class ReviewPlanRepository:
    def __init__(self, store) -> None:
        self.store = store

    def save(self, plan: ReviewPlan) -> str:
        payload = {
            "policy_version": plan.policy_version,
            "symbol": plan.symbol,
            "evaluated_at": plan.evaluated_at.isoformat(),
            "review_mode": plan.mode.value,
            "analysis_depth": plan.analysis_depth.value,
            "reason_codes": list(plan.reason_codes),
            "last_review_at": plan.last_review_at.isoformat() if plan.last_review_at else None,
            "next_review_at": plan.next_review_at.isoformat() if plan.next_review_at else None,
            "routine_full_research_available": plan.routine_full_research_available,
            "budget_override": plan.budget_override,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        plan_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self.store._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO review_plans "
                "(plan_id,policy_version,symbol,evaluated_at,review_mode,analysis_depth,reason_codes,"
                "last_review_at,next_review_at,routine_full_research_available,budget_override,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    plan_id, plan.policy_version, plan.symbol, plan.evaluated_at.isoformat(),
                    plan.mode.value, plan.analysis_depth.value,
                    json.dumps(list(plan.reason_codes), ensure_ascii=False),
                    payload["last_review_at"], payload["next_review_at"],
                    int(plan.routine_full_research_available), int(plan.budget_override),
                    beijing_now().isoformat(),
                ),
            )
        return plan_id

    def latest(self, symbol: str) -> ReviewPlan | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_plans WHERE symbol=? ORDER BY evaluated_at DESC, created_at DESC LIMIT 1",
                (symbol.strip().upper(),),
            ).fetchone()
        if row is None:
            return None
        from datetime import datetime

        return ReviewPlan(
            policy_version=str(row["policy_version"]),
            symbol=str(row["symbol"]),
            evaluated_at=datetime.fromisoformat(str(row["evaluated_at"])),
            mode=ReviewMode(str(row["review_mode"])),
            analysis_depth=AnalysisDepth(str(row["analysis_depth"])),
            reason_codes=tuple(json.loads(str(row["reason_codes"]))),
            last_review_at=datetime.fromisoformat(str(row["last_review_at"])) if row["last_review_at"] else None,
            next_review_at=datetime.fromisoformat(str(row["next_review_at"])) if row["next_review_at"] else None,
            routine_full_research_available=bool(row["routine_full_research_available"]),
            budget_override=bool(row["budget_override"]),
        )

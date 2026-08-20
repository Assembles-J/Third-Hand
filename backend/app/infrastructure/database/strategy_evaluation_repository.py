"""Append-only persistence for immutable N3.4 StrategyEvaluation snapshots."""
from __future__ import annotations

import json

from app.domain.evaluation import StrategyEvaluation


class StrategyEvaluationRepository:
    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS strategy_evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    evaluation_policy_version TEXT NOT NULL,
                    sample_quality_policy_version TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    computed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_strategy_evaluation_experiment
                    ON strategy_evaluations(experiment_id,experiment_version,computed_at);
                """
            )

    def save(self, evaluation: StrategyEvaluation) -> StrategyEvaluation:
        payload_json = evaluation.canonical_json()
        payload_hash = evaluation.contract_hash
        with self.store._connect() as connection:
            existing = connection.execute(
                "SELECT payload_json,payload_hash FROM strategy_evaluations WHERE evaluation_id=?",
                (evaluation.evaluation_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_hash"]) != payload_hash:
                    raise ValueError(
                        "strategy evaluation is immutable: existing identity has different content"
                    )
                return StrategyEvaluation.model_validate(
                    json.loads(str(existing["payload_json"]))
                )
            connection.execute(
                """
                INSERT INTO strategy_evaluations(
                    evaluation_id,experiment_id,experiment_version,
                    evaluation_policy_version,sample_quality_policy_version,
                    source_hash,payload_json,payload_hash,computed_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    evaluation.evaluation_id,
                    evaluation.experiment_id,
                    evaluation.experiment_version,
                    evaluation.evaluation_policy_version,
                    evaluation.sample_quality_policy_version,
                    evaluation.source_hash,
                    payload_json,
                    payload_hash,
                    evaluation.computed_at.isoformat(),
                ),
            )
        return evaluation

    def get(self, evaluation_id: str) -> StrategyEvaluation | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM strategy_evaluations WHERE evaluation_id=?",
                (str(evaluation_id),),
            ).fetchone()
        if row is None:
            return None
        return StrategyEvaluation.model_validate(json.loads(str(row["payload_json"])))

    def latest(
        self,
        experiment_id: str,
        experiment_version: str,
    ) -> StrategyEvaluation | None:
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM strategy_evaluations
                WHERE experiment_id=? AND experiment_version=?
                ORDER BY computed_at DESC,evaluation_id DESC LIMIT 1
                """,
                (str(experiment_id), str(experiment_version)),
            ).fetchone()
        if row is None:
            return None
        return StrategyEvaluation.model_validate(json.loads(str(row["payload_json"])))


__all__ = ["StrategyEvaluationRepository"]

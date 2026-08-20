"""Append-only persistence for terminal N3 outcomes."""
from __future__ import annotations

import json

from app.domain.evaluation import DecisionOutcome, ExecutionOutcome, OutcomeStatus, TradeEpisodeOutcome


class EvaluationOutcomeRepository:
    """Persist resolved/invalid outcomes without rewriting historical evidence.

    PENDING is derived from current observation completeness and is intentionally
    not persisted. Once a terminal outcome is stored, the same identity may be
    written only with identical canonical content.
    """

    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS evaluation_decision_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    horizon_sessions INTEGER NOT NULL,
                    outcome_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    resolved_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_eval_decision_experiment_decision
                    ON evaluation_decision_outcomes(experiment_id,experiment_version,decision_id,horizon_sessions);

                CREATE TABLE IF NOT EXISTS evaluation_execution_outcomes (
                    execution_outcome_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    outcome_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    resolved_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_eval_execution_experiment_decision
                    ON evaluation_execution_outcomes(experiment_id,experiment_version,decision_id);

                CREATE TABLE IF NOT EXISTS evaluation_trade_episode_outcomes (
                    episode_outcome_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    position_episode_id TEXT NOT NULL,
                    outcome_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    resolved_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_eval_episode_experiment_episode
                    ON evaluation_trade_episode_outcomes(experiment_id,experiment_version,position_episode_id);
                """
            )

    def save_decision(self, outcome: DecisionOutcome) -> DecisionOutcome:
        return self._save(
            table="evaluation_decision_outcomes",
            id_column="outcome_id",
            identity=outcome.outcome_id,
            model=outcome,
            extra=(outcome.decision_id, outcome.horizon_sessions),
            insert_columns=("decision_id", "horizon_sessions"),
        )

    def save_execution(self, outcome: ExecutionOutcome) -> ExecutionOutcome:
        return self._save(
            table="evaluation_execution_outcomes",
            id_column="execution_outcome_id",
            identity=outcome.execution_outcome_id,
            model=outcome,
            extra=(outcome.decision_id,),
            insert_columns=("decision_id",),
        )

    def save_episode(self, outcome: TradeEpisodeOutcome) -> TradeEpisodeOutcome:
        return self._save(
            table="evaluation_trade_episode_outcomes",
            id_column="episode_outcome_id",
            identity=outcome.episode_outcome_id,
            model=outcome,
            extra=(outcome.position_episode_id,),
            insert_columns=("position_episode_id",),
        )

    def get_decision(self, outcome_id: str) -> DecisionOutcome | None:
        return self._get("evaluation_decision_outcomes", "outcome_id", outcome_id, DecisionOutcome)

    def get_execution(self, outcome_id: str) -> ExecutionOutcome | None:
        return self._get(
            "evaluation_execution_outcomes", "execution_outcome_id", outcome_id, ExecutionOutcome
        )

    def get_episode(self, outcome_id: str) -> TradeEpisodeOutcome | None:
        return self._get(
            "evaluation_trade_episode_outcomes", "episode_outcome_id", outcome_id, TradeEpisodeOutcome
        )

    def _save(
        self,
        *,
        table: str,
        id_column: str,
        identity: str,
        model,
        extra: tuple[object, ...],
        insert_columns: tuple[str, ...],
    ):
        if model.outcome_status == OutcomeStatus.PENDING:
            raise ValueError("PENDING evaluation outcomes are derived and must not be persisted")
        if model.resolved_at is None:
            raise ValueError("terminal evaluation outcome requires resolved_at")
        payload_json = model.canonical_json()
        payload_hash = model.contract_hash
        with self.store._connect() as connection:
            existing = connection.execute(
                f"SELECT payload_json,payload_hash FROM {table} WHERE {id_column}=?",
                (identity,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_hash"]) != payload_hash:
                    raise ValueError(
                        "evaluation outcome is immutable: existing identity has different content"
                    )
                return type(model).model_validate(json.loads(str(existing["payload_json"])))

            columns = (
                id_column,
                "experiment_id",
                "experiment_version",
                *insert_columns,
                "outcome_status",
                "payload_json",
                "payload_hash",
                "resolved_at",
            )
            values = (
                identity,
                model.experiment_id,
                model.experiment_version,
                *extra,
                model.outcome_status.value,
                payload_json,
                payload_hash,
                model.resolved_at.isoformat(),
            )
            placeholders = ",".join("?" for _ in columns)
            connection.execute(
                f"INSERT INTO {table}({','.join(columns)}) VALUES({placeholders})",
                values,
            )
        return model

    def _get(self, table: str, id_column: str, identity: str, model_type):
        with self.store._connect() as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {table} WHERE {id_column}=?",
                (str(identity),),
            ).fetchone()
        if row is None:
            return None
        return model_type.model_validate(json.loads(str(row["payload_json"])))


__all__ = ["EvaluationOutcomeRepository"]

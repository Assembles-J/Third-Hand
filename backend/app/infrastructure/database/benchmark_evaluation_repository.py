"""Append-only persistence for N3.5 benchmark observations/evaluations."""
from __future__ import annotations

import json

from app.domain.evaluation.benchmarks import BenchmarkEvaluation, BenchmarkObservation
from app.domain.evaluation.common import OutcomeStatus


class BenchmarkEvaluationRepository:
    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS benchmark_observations (
                    benchmark_observation_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    benchmark_policy_version TEXT NOT NULL,
                    decision_outcome_id TEXT NOT NULL,
                    outcome_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    resolved_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_benchmark_obs_experiment
                    ON benchmark_observations(experiment_id, experiment_version, benchmark_policy_version);

                CREATE TABLE IF NOT EXISTS benchmark_evaluations (
                    benchmark_evaluation_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    benchmark_policy_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    computed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_benchmark_eval_experiment
                    ON benchmark_evaluations(experiment_id, experiment_version, computed_at DESC);
                """
            )

    def save_observation(self, observation: BenchmarkObservation) -> BenchmarkObservation:
        if observation.outcome_status == OutcomeStatus.PENDING:
            raise ValueError("PENDING benchmark observations are derived and must not be persisted")
        if observation.resolved_at is None:
            raise ValueError("terminal benchmark observation requires resolved_at")
        return self._save(
            table="benchmark_observations",
            id_column="benchmark_observation_id",
            identity=observation.benchmark_observation_id,
            model=observation,
            extra_columns=(
                "experiment_id",
                "experiment_version",
                "benchmark_policy_version",
                "decision_outcome_id",
                "outcome_status",
                "resolved_at",
            ),
            extra_values=(
                observation.experiment_id,
                observation.experiment_version,
                observation.benchmark_policy_version,
                observation.decision_outcome_id,
                observation.outcome_status.value,
                observation.resolved_at.isoformat(),
            ),
        )

    def get_observation(self, observation_id: str) -> BenchmarkObservation | None:
        return self._get(
            "benchmark_observations",
            "benchmark_observation_id",
            observation_id,
            BenchmarkObservation,
        )

    def list_observations(
        self,
        experiment_id: str,
        experiment_version: str,
        benchmark_policy_version: str,
    ) -> tuple[BenchmarkObservation, ...]:
        with self.store._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM benchmark_observations
                WHERE experiment_id=? AND experiment_version=? AND benchmark_policy_version=?
                ORDER BY benchmark_observation_id ASC
                """,
                (experiment_id, experiment_version, benchmark_policy_version),
            ).fetchall()
        return tuple(
            BenchmarkObservation.model_validate(json.loads(str(row["payload_json"])))
            for row in rows
        )

    def save_evaluation(self, evaluation: BenchmarkEvaluation) -> BenchmarkEvaluation:
        return self._save(
            table="benchmark_evaluations",
            id_column="benchmark_evaluation_id",
            identity=evaluation.benchmark_evaluation_id,
            model=evaluation,
            extra_columns=(
                "experiment_id",
                "experiment_version",
                "benchmark_policy_version",
                "computed_at",
            ),
            extra_values=(
                evaluation.experiment_id,
                evaluation.experiment_version,
                evaluation.benchmark_policy_version,
                evaluation.computed_at.isoformat(),
            ),
        )

    def get_evaluation(self, evaluation_id: str) -> BenchmarkEvaluation | None:
        return self._get(
            "benchmark_evaluations",
            "benchmark_evaluation_id",
            evaluation_id,
            BenchmarkEvaluation,
        )

    def latest_evaluation(
        self,
        experiment_id: str,
        experiment_version: str,
    ) -> BenchmarkEvaluation | None:
        """Return the latest immutable benchmark snapshot for one experiment version."""
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM benchmark_evaluations
                WHERE experiment_id=? AND experiment_version=?
                ORDER BY computed_at DESC, benchmark_evaluation_id DESC
                LIMIT 1
                """,
                (str(experiment_id), str(experiment_version)),
            ).fetchone()
        if row is None:
            return None
        return BenchmarkEvaluation.model_validate(json.loads(str(row["payload_json"])))

    def _save(
        self,
        *,
        table: str,
        id_column: str,
        identity: str,
        model,
        extra_columns: tuple[str, ...],
        extra_values: tuple[object, ...],
    ):
        payload_json = model.canonical_json()
        payload_hash = model.contract_hash
        with self.store._connect() as connection:
            existing = connection.execute(
                f"SELECT payload_json,payload_hash FROM {table} WHERE {id_column}=?",
                (identity,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_hash"]) != payload_hash:
                    raise ValueError("benchmark record is immutable: existing identity has different content")
                return type(model).model_validate(json.loads(str(existing["payload_json"])))

            columns = (id_column, *extra_columns, "payload_json", "payload_hash")
            values = (identity, *extra_values, payload_json, payload_hash)
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


__all__ = ["BenchmarkEvaluationRepository"]

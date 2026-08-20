"""Append-only SQLite persistence for immutable experiment definitions."""
from __future__ import annotations

import json

from app.domain.experiment import ExperimentDefinition


class ExperimentDefinitionRepository:
    """Persist experiment identity/version lineage without runtime authority."""

    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_definitions (
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    experiment_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    definition_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (experiment_id, experiment_version)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_experiment_strategy_created "
                "ON experiment_definitions(strategy_id, strategy_version, created_at DESC)"
            )

    def save(self, definition: ExperimentDefinition) -> ExperimentDefinition:
        payload_json = definition.canonical_json()
        definition_hash = definition.definition_hash
        identity = (definition.experiment_id, definition.experiment_version)

        with self.store._connect() as connection:
            existing = connection.execute(
                """
                SELECT payload_json, definition_hash
                FROM experiment_definitions
                WHERE experiment_id=? AND experiment_version=?
                """,
                identity,
            ).fetchone()
            if existing is not None:
                if str(existing["definition_hash"]) != definition_hash:
                    raise ValueError(
                        "experiment definition is immutable: existing id/version has different content"
                    )
                return ExperimentDefinition.model_validate(json.loads(str(existing["payload_json"])))

            connection.execute(
                """
                INSERT INTO experiment_definitions(
                    experiment_id, experiment_version, experiment_type, status,
                    strategy_id, strategy_version, payload_json, definition_hash, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    definition.experiment_id,
                    definition.experiment_version,
                    definition.experiment_type.value,
                    definition.status.value,
                    definition.strategy_id,
                    definition.strategy_version,
                    payload_json,
                    definition_hash,
                    definition.created_at.isoformat(),
                ),
            )
        return definition

    def get(self, experiment_id: str, experiment_version: str) -> ExperimentDefinition | None:
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM experiment_definitions
                WHERE experiment_id=? AND experiment_version=?
                """,
                (str(experiment_id).strip(), str(experiment_version).strip()),
            ).fetchone()
        if row is None:
            return None
        return ExperimentDefinition.model_validate(json.loads(str(row["payload_json"])))

    def list_for_strategy(
        self,
        strategy_id: str,
        strategy_version: str | None = None,
    ) -> tuple[ExperimentDefinition, ...]:
        normalized_strategy = str(strategy_id).strip()
        with self.store._connect() as connection:
            if strategy_version is None:
                rows = connection.execute(
                    """
                    SELECT payload_json FROM experiment_definitions
                    WHERE strategy_id=?
                    ORDER BY created_at DESC, experiment_id, experiment_version
                    """,
                    (normalized_strategy,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT payload_json FROM experiment_definitions
                    WHERE strategy_id=? AND strategy_version=?
                    ORDER BY created_at DESC, experiment_id, experiment_version
                    """,
                    (normalized_strategy, str(strategy_version).strip()),
                ).fetchall()
        return tuple(
            ExperimentDefinition.model_validate(json.loads(str(row["payload_json"])))
            for row in rows
        )


__all__ = ["ExperimentDefinitionRepository"]

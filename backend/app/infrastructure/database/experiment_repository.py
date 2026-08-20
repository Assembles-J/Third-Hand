"""Append-only SQLite persistence for immutable N3 experiment identity."""
from __future__ import annotations

import json

from app.domain.experiment import ExperimentDefinition, ExperimentUniverseSnapshot


class ExperimentDefinitionRepository:
    """Persist experiment definitions and their exact frozen membership.

    Every experiment version owns exactly one ExperimentUniverseSnapshot.
    Definitions are rejected unless the linked snapshot already exists and its
    experiment/version, policy version, and deterministic hash all match.
    """

    def __init__(self, store) -> None:
        self.store = store
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.store._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiment_universe_snapshots (
                    universe_snapshot_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    universe_policy_version TEXT NOT NULL,
                    member_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    snapshot_hash TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    UNIQUE(experiment_id, experiment_version)
                );
                CREATE INDEX IF NOT EXISTS idx_experiment_universe_experiment
                    ON experiment_universe_snapshots(experiment_id, experiment_version);

                CREATE TABLE IF NOT EXISTS experiment_definitions (
                    experiment_id TEXT NOT NULL,
                    experiment_version TEXT NOT NULL,
                    experiment_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    universe_snapshot_id TEXT NOT NULL,
                    universe_snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    definition_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (experiment_id, experiment_version)
                );
                CREATE INDEX IF NOT EXISTS idx_experiment_strategy_created
                    ON experiment_definitions(strategy_id, strategy_version, created_at DESC);
                """
            )

    def save_universe(self, snapshot: ExperimentUniverseSnapshot) -> ExperimentUniverseSnapshot:
        payload_json = snapshot.canonical_json()
        snapshot_hash = snapshot.snapshot_hash
        with self.store._connect() as connection:
            existing = connection.execute(
                """
                SELECT universe_snapshot_id, payload_json, snapshot_hash
                FROM experiment_universe_snapshots
                WHERE universe_snapshot_id=?
                   OR (experiment_id=? AND experiment_version=?)
                """,
                (
                    snapshot.universe_snapshot_id,
                    snapshot.experiment_id,
                    snapshot.experiment_version,
                ),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["universe_snapshot_id"]) != snapshot.universe_snapshot_id
                    or str(existing["snapshot_hash"]) != snapshot_hash
                ):
                    raise ValueError(
                        "experiment universe is immutable: existing experiment version has different membership"
                    )
                return ExperimentUniverseSnapshot.model_validate(
                    json.loads(str(existing["payload_json"]))
                )

            connection.execute(
                """
                INSERT INTO experiment_universe_snapshots(
                    universe_snapshot_id, experiment_id, experiment_version,
                    universe_policy_version, member_count, payload_json,
                    snapshot_hash, captured_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    snapshot.universe_snapshot_id,
                    snapshot.experiment_id,
                    snapshot.experiment_version,
                    snapshot.universe_policy_version,
                    len(snapshot.members),
                    payload_json,
                    snapshot_hash,
                    snapshot.captured_at.isoformat(),
                ),
            )
        return snapshot

    def get_universe(self, universe_snapshot_id: str) -> ExperimentUniverseSnapshot | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM experiment_universe_snapshots WHERE universe_snapshot_id=?",
                (str(universe_snapshot_id).strip(),),
            ).fetchone()
        if row is None:
            return None
        return ExperimentUniverseSnapshot.model_validate(json.loads(str(row["payload_json"])))

    def get_universe_for_experiment(
        self,
        experiment_id: str,
        experiment_version: str,
    ) -> ExperimentUniverseSnapshot | None:
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM experiment_universe_snapshots
                WHERE experiment_id=? AND experiment_version=?
                """,
                (str(experiment_id).strip(), str(experiment_version).strip()),
            ).fetchone()
        if row is None:
            return None
        return ExperimentUniverseSnapshot.model_validate(json.loads(str(row["payload_json"])))

    def save(self, definition: ExperimentDefinition) -> ExperimentDefinition:
        snapshot = self.get_universe(definition.universe_snapshot_id)
        if snapshot is None:
            raise ValueError("experiment definition requires a persisted universe snapshot")
        if (
            snapshot.experiment_id != definition.experiment_id
            or snapshot.experiment_version != definition.experiment_version
        ):
            raise ValueError("experiment universe belongs to a different experiment/version")
        if snapshot.universe_policy_version != definition.universe_policy_version:
            raise ValueError("experiment universe policy version does not match definition")
        if snapshot.snapshot_hash != definition.universe_snapshot_hash:
            raise ValueError("experiment universe hash does not match definition")

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
                    strategy_id, strategy_version, universe_snapshot_id,
                    universe_snapshot_hash, payload_json, definition_hash, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    definition.experiment_id,
                    definition.experiment_version,
                    definition.experiment_type.value,
                    definition.status.value,
                    definition.strategy_id,
                    definition.strategy_version,
                    definition.universe_snapshot_id,
                    definition.universe_snapshot_hash,
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

    def latest(self, experiment_id: str) -> ExperimentDefinition | None:
        """Return the latest immutable version by creation time, never by semantic version guessing."""
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM experiment_definitions
                WHERE experiment_id=?
                ORDER BY created_at DESC, experiment_version DESC
                LIMIT 1
                """,
                (str(experiment_id).strip(),),
            ).fetchone()
        if row is None:
            return None
        return ExperimentDefinition.model_validate(json.loads(str(row["payload_json"])))

    def list(
        self,
        *,
        strategy_id: str | None = None,
        experiment_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> tuple[ExperimentDefinition, ...]:
        clauses: list[str] = []
        parameters: list[object] = []
        if strategy_id is not None:
            normalized = str(strategy_id).strip()
            if not normalized:
                raise ValueError("strategy_id filter must not be blank")
            clauses.append("strategy_id=?")
            parameters.append(normalized)
        if experiment_type is not None:
            normalized = str(experiment_type).strip().upper()
            if not normalized:
                raise ValueError("experiment_type filter must not be blank")
            clauses.append("experiment_type=?")
            parameters.append(normalized)
        if status is not None:
            normalized = str(status).strip().upper()
            if not normalized:
                raise ValueError("status filter must not be blank")
            clauses.append("status=?")
            parameters.append(normalized)
        bounded_limit = max(1, min(int(limit), 1000))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.store._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json FROM experiment_definitions
                {where}
                ORDER BY created_at DESC, experiment_id, experiment_version
                LIMIT ?
                """,
                (*parameters, bounded_limit),
            ).fetchall()
        return tuple(
            ExperimentDefinition.model_validate(json.loads(str(row["payload_json"])))
            for row in rows
        )

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

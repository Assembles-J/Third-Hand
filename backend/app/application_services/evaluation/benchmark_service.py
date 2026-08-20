"""N3.5 benchmark alignment over frozen experiment outcomes and local market data."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Mapping

from app.domain.evaluation import OutcomeStatus
from app.domain.evaluation.benchmarks import (
    BenchmarkConstituentSource,
    BenchmarkEvaluation,
    BenchmarkHorizonSummary,
    BenchmarkObservation,
    BenchmarkPolicy,
    BenchmarkType,
)
from app.trading_calendar import TradingCalendarService


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except Exception:
        return None
    return result if result.is_finite() else None


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


class BenchmarkEvaluationService:
    """Compare resolved DecisionOutcomes with explicit point-in-time baselines.

    This service deliberately computes *decision-window* relative returns only.
    Account-level benchmark/excess return remains unavailable until N3 has a
    trustworthy experiment equity curve and an aligned benchmark equity curve.
    """

    def __init__(
        self,
        outcome_repository,
        source_repository,
        *,
        experiment_repository=None,
        benchmark_repository=None,
        trading_calendar: TradingCalendarService | None = None,
    ) -> None:
        self.outcomes = outcome_repository
        self.source = source_repository
        self.experiments = experiment_repository
        self.benchmarks = benchmark_repository
        self.calendar = trading_calendar or TradingCalendarService()

    def evaluate(
        self,
        experiment,
        policy: BenchmarkPolicy,
        *,
        computed_at: datetime,
    ) -> BenchmarkEvaluation:
        if computed_at.tzinfo is None:
            raise ValueError("benchmark computed_at must include timezone information")
        if str(experiment.benchmark_policy_version) != policy.version:
            raise ValueError("experiment benchmark_policy_version does not match benchmark policy")

        universe = self._require_universe(experiment)
        decisions = tuple(
            item
            for item in self.outcomes.list_decisions(
                experiment.experiment_id,
                experiment.experiment_version,
            )
            if item.outcome_status == OutcomeStatus.RESOLVED
        )

        observations = tuple(
            self._resolve_observation(
                experiment,
                universe,
                policy,
                item,
                computed_at=computed_at,
            )
            for item in decisions
        )

        resolved = [item for item in observations if item.outcome_status == OutcomeStatus.RESOLVED]
        nonresolved = [item for item in observations if item.outcome_status != OutcomeStatus.RESOLVED]

        groups: dict[tuple[str, int], list[BenchmarkObservation]] = defaultdict(list)
        for item in observations:
            groups[(item.market, item.horizon_sessions)].append(item)
        breakdown: list[BenchmarkHorizonSummary] = []
        for (market, horizon), items in sorted(groups.items()):
            group_resolved = [item for item in items if item.outcome_status == OutcomeStatus.RESOLVED]
            group_nonresolved = [item for item in items if item.outcome_status != OutcomeStatus.RESOLVED]
            breakdown.append(
                BenchmarkHorizonSummary(
                    market=market,
                    horizon_sessions=horizon,
                    resolved_count=len(group_resolved),
                    nonresolved_count=len(group_nonresolved),
                    mean_strategy_forward_return=_mean(
                        [item.strategy_forward_return for item in group_resolved if item.strategy_forward_return is not None]
                    ),
                    mean_benchmark_forward_return=_mean(
                        [item.benchmark_forward_return for item in group_resolved if item.benchmark_forward_return is not None]
                    ),
                    mean_excess_forward_return=_mean(
                        [item.excess_forward_return for item in group_resolved if item.excess_forward_return is not None]
                    ),
                )
            )

        lineage = {
            "experiment_id": experiment.experiment_id,
            "experiment_version": experiment.experiment_version,
            "universe_snapshot_hash": universe.snapshot_hash,
            "benchmark_policy_hash": policy.contract_hash,
            "observation_hashes": sorted(item.contract_hash for item in observations),
        }
        source_hash = _canonical_hash(lineage)
        evaluation_id = (
            f"{experiment.experiment_id}:{experiment.experiment_version}:benchmark:"
            f"{policy.version}:{source_hash[:20]}:{computed_at.isoformat()}"
        )
        result = BenchmarkEvaluation(
            benchmark_evaluation_id=evaluation_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            universe_snapshot_id=universe.universe_snapshot_id,
            universe_snapshot_hash=universe.snapshot_hash,
            benchmark_policy_id=policy.benchmark_policy_id,
            benchmark_policy_version=policy.version,
            benchmark_type=policy.benchmark_type,
            computed_at=computed_at,
            resolved_observation_count=len(resolved),
            nonresolved_observation_count=len(nonresolved),
            mean_strategy_forward_return=_mean(
                [item.strategy_forward_return for item in resolved if item.strategy_forward_return is not None]
            ),
            mean_benchmark_forward_return=_mean(
                [item.benchmark_forward_return for item in resolved if item.benchmark_forward_return is not None]
            ),
            mean_excess_forward_return=_mean(
                [item.excess_forward_return for item in resolved if item.excess_forward_return is not None]
            ),
            horizon_breakdown=tuple(breakdown),
            portfolio_benchmark_return=None,
            portfolio_excess_return=None,
            portfolio_metric_reason_codes=(
                "experiment_and_benchmark_equity_curves_unavailable_n3_5",
            ),
            source_hash=source_hash,
        )
        if self.benchmarks is not None:
            return self.benchmarks.save_evaluation(result)
        return result

    def _resolve_observation(
        self,
        experiment,
        universe,
        policy: BenchmarkPolicy,
        decision,
        *,
        computed_at: datetime,
    ) -> BenchmarkObservation:
        if not universe.contains(decision.symbol, decision.market):
            raise ValueError("decision outcome is outside frozen experiment universe")
        identity = (
            f"{experiment.experiment_id}:{experiment.experiment_version}:"
            f"{decision.outcome_id}:benchmark:{policy.version}"
        )
        if self.benchmarks is not None:
            existing = self.benchmarks.get_observation(identity)
            if existing is not None:
                return existing

        reference_session = self.calendar.latest_completed_session_date(
            decision.market,
            decision.decision_time,
        )
        end_session = self.calendar.latest_completed_session_date(
            decision.market,
            decision.observation_end,
        )
        if reference_session is None or end_session is None or end_session < reference_session:
            return self._terminal_nonresolved(
                experiment,
                universe,
                policy,
                decision,
                identity,
                computed_at,
                OutcomeStatus.INVALID,
                ("benchmark_alignment_session_unavailable",),
                reference_session=reference_session,
                end_session=end_session,
            )

        if policy.benchmark_type == BenchmarkType.FORMAL_SWING_V1:
            return self._terminal_nonresolved(
                experiment,
                universe,
                policy,
                decision,
                identity,
                computed_at,
                OutcomeStatus.INVALID,
                ("reference_strategy_benchmark_requires_evaluation_compare_v1",),
                reference_session=reference_session,
                end_session=end_session,
            )

        if policy.benchmark_type == BenchmarkType.NEUTRAL_DIAGNOSTIC:
            benchmark_return = Decimal("0")
            members: tuple[tuple[str, str], ...] = ()
            source_rows: object = {"diagnostic": "zero_return"}
        elif policy.benchmark_type in {BenchmarkType.MARKET_INDEX, BenchmarkType.BUY_AND_HOLD_SYMBOL}:
            if decision.market != policy.benchmark_market:
                return self._terminal_nonresolved(
                    experiment,
                    universe,
                    policy,
                    decision,
                    identity,
                    computed_at,
                    OutcomeStatus.INVALID,
                    ("benchmark_market_mismatch",),
                    reference_session=reference_session,
                    end_session=end_session,
                )
            result = self._symbol_return(
                policy.benchmark_symbol,
                reference_session,
                end_session,
            )
            if result is None:
                return self._terminal_nonresolved(
                    experiment,
                    universe,
                    policy,
                    decision,
                    identity,
                    computed_at,
                    OutcomeStatus.INSUFFICIENT_DATA,
                    ("benchmark_symbol_history_incomplete",),
                    reference_session=reference_session,
                    end_session=end_session,
                )
            benchmark_return, source_rows = result
            members = ((policy.benchmark_market, policy.benchmark_symbol),)
        elif policy.benchmark_type == BenchmarkType.EQUAL_WEIGHT_ELIGIBLE_UNIVERSE:
            eligible = tuple(
                (item.market, item.symbol)
                for item in universe.members
                if item.market == decision.market
            )
            if not eligible:
                return self._terminal_nonresolved(
                    experiment,
                    universe,
                    policy,
                    decision,
                    identity,
                    computed_at,
                    OutcomeStatus.INVALID,
                    ("benchmark_universe_has_no_same_market_members",),
                    reference_session=reference_session,
                    end_session=end_session,
                )
            component_returns: list[Decimal] = []
            component_rows: list[object] = []
            for market, symbol in eligible:
                result = self._symbol_return(symbol, reference_session, end_session)
                if result is None:
                    return self._terminal_nonresolved(
                        experiment,
                        universe,
                        policy,
                        decision,
                        identity,
                        computed_at,
                        OutcomeStatus.INSUFFICIENT_DATA,
                        ("benchmark_equal_weight_constituent_history_incomplete",),
                        reference_session=reference_session,
                        end_session=end_session,
                    )
                value, rows = result
                component_returns.append(value)
                component_rows.append({"market": market, "symbol": symbol, "rows": rows})
            benchmark_return = _mean(component_returns)
            if benchmark_return is None:
                raise ValueError("equal-weight benchmark unexpectedly has no returns")
            members = eligible
            source_rows = component_rows
        else:
            raise ValueError(f"unsupported benchmark type: {policy.benchmark_type}")

        if policy.cost_assumption_bps:
            benchmark_return -= policy.cost_assumption_bps / Decimal("10000")

        constituent_hash = _canonical_hash(members) if members else None
        lineage = {
            "decision_outcome_hash": decision.contract_hash,
            "benchmark_policy_hash": policy.contract_hash,
            "universe_snapshot_hash": universe.snapshot_hash,
            "reference_session": reference_session,
            "end_session": end_session,
            "members": members,
            "source_rows": source_rows,
        }
        observation = BenchmarkObservation(
            benchmark_observation_id=identity,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            universe_snapshot_id=universe.universe_snapshot_id,
            universe_snapshot_hash=universe.snapshot_hash,
            benchmark_policy_id=policy.benchmark_policy_id,
            benchmark_policy_version=policy.version,
            benchmark_type=policy.benchmark_type,
            decision_outcome_id=decision.outcome_id,
            decision_id=decision.decision_id,
            strategy_symbol=decision.symbol,
            market=decision.market,
            horizon_sessions=decision.horizon_sessions,
            decision_time=decision.decision_time,
            observation_end=decision.observation_end,
            reference_session=reference_session,
            end_session=end_session,
            outcome_status=OutcomeStatus.RESOLVED,
            strategy_forward_return=decision.forward_return,
            benchmark_forward_return=benchmark_return,
            excess_forward_return=decision.forward_return - benchmark_return,
            constituent_count=len(members),
            constituent_hash=constituent_hash,
            source_lineage_hash=_canonical_hash(lineage),
            resolved_at=computed_at,
        )
        if self.benchmarks is not None:
            return self.benchmarks.save_observation(observation)
        return observation

    def _symbol_return(
        self,
        symbol: str | None,
        reference_session: str,
        end_session: str,
    ) -> tuple[Decimal, object] | None:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            return None
        rows = tuple(self.source.daily_bars_between(normalized, reference_session, end_session))
        by_date = {str(row.get("trading_date")): row for row in rows}
        start = by_date.get(reference_session)
        end = by_date.get(end_session)
        if not self._eligible_bar(start) or not self._eligible_bar(end):
            return None
        start_close = _decimal(start.get("close"))
        end_close = _decimal(end.get("close"))
        if start_close is None or end_close is None or start_close <= 0 or end_close <= 0:
            return None
        return end_close / start_close - 1, {
            "start": dict(start),
            "end": dict(end),
        }

    @staticmethod
    def _eligible_bar(row: Mapping[str, object] | None) -> bool:
        if not isinstance(row, Mapping):
            return False
        close = _decimal(row.get("close"))
        adjustment = str(row.get("adjustment") or "").strip().lower()
        return close is not None and close > 0 and adjustment == "qfq"

    def _terminal_nonresolved(
        self,
        experiment,
        universe,
        policy,
        decision,
        identity: str,
        computed_at: datetime,
        status: OutcomeStatus,
        reasons: tuple[str, ...],
        *,
        reference_session: str | None,
        end_session: str | None,
    ) -> BenchmarkObservation:
        lineage = {
            "decision_outcome_hash": decision.contract_hash,
            "benchmark_policy_hash": policy.contract_hash,
            "universe_snapshot_hash": universe.snapshot_hash,
            "reference_session": reference_session,
            "end_session": end_session,
            "reason_codes": reasons,
        }
        result = BenchmarkObservation(
            benchmark_observation_id=identity,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            universe_snapshot_id=universe.universe_snapshot_id,
            universe_snapshot_hash=universe.snapshot_hash,
            benchmark_policy_id=policy.benchmark_policy_id,
            benchmark_policy_version=policy.version,
            benchmark_type=policy.benchmark_type,
            decision_outcome_id=decision.outcome_id,
            decision_id=decision.decision_id,
            strategy_symbol=decision.symbol,
            market=decision.market,
            horizon_sessions=decision.horizon_sessions,
            decision_time=decision.decision_time,
            observation_end=decision.observation_end,
            reference_session=reference_session,
            end_session=end_session,
            outcome_status=status,
            reason_codes=reasons,
            source_lineage_hash=_canonical_hash(lineage),
            resolved_at=computed_at,
        )
        if self.benchmarks is not None:
            return self.benchmarks.save_observation(result)
        return result

    def _require_universe(self, experiment):
        snapshot = getattr(experiment, "universe_snapshot", None)
        if snapshot is None:
            if self.experiments is None:
                raise ValueError("experiment universe repository is required for benchmark evaluation")
            snapshot = self.experiments.get_universe(experiment.universe_snapshot_id)
        if snapshot is None:
            raise ValueError("experiment universe snapshot not found")
        if snapshot.universe_snapshot_id != experiment.universe_snapshot_id:
            raise ValueError("experiment universe snapshot identity mismatch")
        if snapshot.snapshot_hash != experiment.universe_snapshot_hash:
            raise ValueError("experiment universe snapshot hash mismatch")
        if snapshot.experiment_id != experiment.experiment_id or snapshot.experiment_version != experiment.experiment_version:
            raise ValueError("experiment universe belongs to a different experiment/version")
        if snapshot.universe_policy_version != experiment.universe_policy_version:
            raise ValueError("experiment universe policy version mismatch")
        return snapshot


__all__ = ["BenchmarkEvaluationService"]

"""N3.4 deterministic aggregation over immutable terminal evaluation outcomes."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json

from app.domain.evaluation import OutcomeStatus
from app.market_adapter import market_for_symbol
from app.domain.evaluation.strategy_evaluation import (
    DecisionMetricBreakdown,
    EvaluationPolicy,
    ExecutionDispositionCount,
    SampleQualityPolicy,
    StrategyEvaluation,
    swing_v1_evaluation_policy,
    swing_v1_sample_quality_policy,
)


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _max_consecutive_losses(episodes) -> int:
    streak = maximum = 0
    for episode in sorted(
        episodes,
        key=lambda item: (item.closed_at, item.episode_outcome_id),
    ):
        if episode.net_return is not None and episode.net_return < 0:
            streak += 1
            maximum = max(maximum, streak)
        else:
            streak = 0
    return maximum


def _decision_breakdown(
    items,
    *,
    action=None,
    regime=None,
    horizon=None,
) -> DecisionMetricBreakdown:
    selected = [item for item in items if item.outcome_status == OutcomeStatus.RESOLVED]
    if action is not None:
        selected = [item for item in selected if item.action == action]
    if regime is not None:
        selected = [item for item in selected if (item.market_regime or "UNKNOWN") == regime]
    if horizon is not None:
        selected = [item for item in selected if item.horizon_sessions == horizon]
    if not selected:
        raise ValueError("decision breakdown requires at least one resolved outcome")
    effective_horizon = horizon if horizon is not None else selected[0].horizon_sessions
    classes = [item.action_outcome_class for item in selected]
    return DecisionMetricBreakdown(
        action=action,
        market_regime=regime,
        horizon_sessions=effective_horizon,
        sample_count=len(selected),
        favorable_count=sum(value == "FAVORABLE" for value in classes),
        unfavorable_count=sum(value == "UNFAVORABLE" for value in classes),
        mixed_count=sum(value == "MIXED" for value in classes),
        neutral_count=sum(value == "NEUTRAL" for value in classes),
        not_applicable_count=sum(value == "NOT_APPLICABLE" for value in classes),
        mean_forward_return=_mean(
            [item.forward_return for item in selected if item.forward_return is not None]
        ),
        mean_mfe=_mean([item.mfe for item in selected if item.mfe is not None]),
        mean_mae=_mean([item.mae for item in selected if item.mae is not None]),
    )


class StrategyEvaluationService:
    """Build immutable evaluation snapshots without benchmark or trading authority."""

    def __init__(
        self,
        outcome_repository,
        *,
        evaluation_repository=None,
        experiment_repository=None,
        evaluation_policy: EvaluationPolicy | None = None,
        sample_quality_policy: SampleQualityPolicy | None = None,
    ) -> None:
        self.outcomes = outcome_repository
        self.evaluations = evaluation_repository
        self.experiments = experiment_repository
        self.policy = evaluation_policy or swing_v1_evaluation_policy()
        self.sample_policy = sample_quality_policy or swing_v1_sample_quality_policy()

    def evaluate(self, experiment, *, computed_at: datetime) -> StrategyEvaluation:
        if computed_at.tzinfo is None:
            raise ValueError("computed_at must include timezone information")
        if str(experiment.evaluation_policy_version) != self.policy.version:
            raise ValueError(
                "experiment evaluation_policy_version does not match evaluation policy"
            )
        if str(experiment.sample_quality_policy_version) != self.sample_policy.version:
            raise ValueError(
                "experiment sample_quality_policy_version does not match sample policy"
            )
        universe = self._require_universe(experiment)

        decisions = tuple(
            self.outcomes.list_decisions(
                experiment.experiment_id,
                experiment.experiment_version,
            )
        )
        executions = tuple(
            self.outcomes.list_executions(
                experiment.experiment_id,
                experiment.experiment_version,
            )
        )
        episodes = tuple(
            self.outcomes.list_episodes(
                experiment.experiment_id,
                experiment.experiment_version,
            )
        )

        for item in decisions:
            if not universe.contains(item.symbol, item.market):
                raise ValueError("decision outcome is outside frozen experiment universe")
        for item in episodes:
            market = market_for_symbol(item.symbol)
            if market is None or not universe.contains(item.symbol, market):
                raise ValueError("trade episode outcome is outside frozen experiment universe")

        resolved_decision_rows = [
            item for item in decisions if item.outcome_status == OutcomeStatus.RESOLVED
        ]
        nonresolved_decision_rows = [
            item
            for item in decisions
            if item.outcome_status
            in {OutcomeStatus.INSUFFICIENT_DATA, OutcomeStatus.INVALID}
        ]
        terminal_decision_rows = resolved_decision_rows + nonresolved_decision_rows
        resolved_decision_ids = {item.decision_id for item in resolved_decision_rows}
        resolved_episodes = [
            item for item in episodes if item.outcome_status == OutcomeStatus.RESOLVED
        ]

        expected_outcome_policy = str(experiment.outcome_policy_version)
        observed_outcome_policies = {
            item.outcome_policy_version for item in decisions + episodes
        }
        mismatched_outcome_policies = observed_outcome_policies - {expected_outcome_policy}
        if mismatched_outcome_policies:
            raise ValueError(
                "stored outcomes do not match experiment outcome_policy_version: "
                f"{sorted(mismatched_outcome_policies)}"
            )

        symbols = {item.symbol for item in resolved_decision_rows} | {
            item.symbol for item in resolved_episodes
        }
        nonresolved_ratio = (
            Decimal(len(nonresolved_decision_rows))
            / Decimal(len(terminal_decision_rows))
            if terminal_decision_rows
            else Decimal("0")
        )
        sample_quality = self.sample_policy.classify(
            resolved_decisions=len(resolved_decision_ids),
            completed_episodes=len(resolved_episodes),
            distinct_symbols=len(symbols),
            nonresolved_ratio=nonresolved_ratio,
        )

        returns = [
            item.net_return for item in resolved_episodes if item.net_return is not None
        ]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        win_rate = Decimal(len(wins)) / Decimal(len(returns)) if returns else None
        average_win = _mean(wins)
        average_loss = _mean(losses)
        payoff_ratio = (
            average_win / abs(average_loss)
            if average_win is not None
            and average_loss is not None
            and average_loss != 0
            else None
        )
        expectancy = (
            win_rate * (average_win or Decimal("0"))
            + (Decimal("1") - win_rate) * (average_loss or Decimal("0"))
            if win_rate is not None
            else None
        )
        positive_pnl = sum(
            (
                item.realized_pnl
                for item in resolved_episodes
                if item.realized_pnl is not None and item.realized_pnl > 0
            ),
            Decimal("0"),
        )
        negative_pnl = sum(
            (
                item.realized_pnl
                for item in resolved_episodes
                if item.realized_pnl is not None and item.realized_pnl < 0
            ),
            Decimal("0"),
        )
        profit_factor = positive_pnl / abs(negative_pnl) if negative_pnl < 0 else None

        action_breakdown = []
        for action, horizon in sorted(
            {(item.action, item.horizon_sessions) for item in resolved_decision_rows},
            key=lambda key: (str(key[0]), key[1]),
        ):
            action_breakdown.append(
                _decision_breakdown(
                    resolved_decision_rows,
                    action=action,
                    horizon=horizon,
                )
            )

        regime_breakdown = []
        for regime, horizon in sorted(
            {
                ((item.market_regime or "UNKNOWN"), item.horizon_sessions)
                for item in resolved_decision_rows
            }
        ):
            regime_breakdown.append(
                _decision_breakdown(
                    resolved_decision_rows,
                    regime=regime,
                    horizon=horizon,
                )
            )

        horizon_breakdown = [
            _decision_breakdown(resolved_decision_rows, horizon=horizon)
            for horizon in sorted(
                {item.horizon_sessions for item in resolved_decision_rows}
            )
        ]

        execution_groups = defaultdict(lambda: [0, 0])
        for item in executions:
            bucket = execution_groups[item.execution_disposition]
            if item.outcome_status == OutcomeStatus.RESOLVED:
                bucket[0] += 1
            else:
                bucket[1] += 1
        execution_attribution = tuple(
            ExecutionDispositionCount(
                disposition=disposition,
                count=resolved + nonresolved,
                resolved_count=resolved,
                nonresolved_count=nonresolved,
            )
            for disposition, (resolved, nonresolved) in sorted(
                execution_groups.items(),
                key=lambda pair: pair[0].value,
            )
        )

        period_candidates_start = [item.decision_time for item in decisions] + [
            item.opened_at for item in episodes
        ]
        period_candidates_end = [item.observation_end for item in decisions] + [
            item.closed_at or item.resolved_at
            for item in episodes
            if (item.closed_at or item.resolved_at) is not None
        ]
        period_start = min(period_candidates_start) if period_candidates_start else None
        period_end = max(period_candidates_end) if period_candidates_end else None

        lineage = {
            "experiment_id": experiment.experiment_id,
            "experiment_version": experiment.experiment_version,
            "outcome_policy_version": expected_outcome_policy,
            "evaluation_policy_hash": self.policy.contract_hash,
            "sample_quality_policy_hash": self.sample_policy.contract_hash,
            "universe_snapshot_hash": universe.snapshot_hash,
            "decision_outcome_hashes": sorted(item.contract_hash for item in decisions),
            "execution_outcome_hashes": sorted(item.contract_hash for item in executions),
            "episode_outcome_hashes": sorted(item.contract_hash for item in episodes),
        }
        source_hash = _canonical_hash(lineage)
        snapshot_hash = _canonical_hash(
            {
                "source_hash": source_hash,
                "computed_at": computed_at.isoformat(),
            }
        )
        evaluation_id = (
            f"{experiment.experiment_id}:{experiment.experiment_version}:"
            f"{self.policy.version}:{snapshot_hash[:20]}"
        )
        outcome_policy_versions = tuple(
            sorted(observed_outcome_policies or {expected_outcome_policy})
        )

        result = StrategyEvaluation(
            evaluation_id=evaluation_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            universe_snapshot_id=universe.universe_snapshot_id,
            universe_snapshot_hash=universe.snapshot_hash,
            evaluation_policy_version=self.policy.version,
            sample_quality_policy_version=self.sample_policy.version,
            outcome_policy_versions=outcome_policy_versions,
            period_start=period_start,
            period_end=period_end,
            computed_at=computed_at,
            resolved_decision_count=len(resolved_decision_ids),
            decision_outcome_row_count=len(terminal_decision_rows),
            nonresolved_decision_outcome_count=len(nonresolved_decision_rows),
            completed_trade_count=len(resolved_episodes),
            distinct_symbol_count=len(symbols),
            sample_quality=sample_quality,
            nonresolved_ratio=nonresolved_ratio,
            total_return=None,
            max_drawdown=None,
            portfolio_metric_reason_codes=(
                "experiment_equity_curve_unavailable_n3_4",
            ),
            win_rate=win_rate,
            average_win=average_win,
            average_loss=average_loss,
            payoff_ratio=payoff_ratio,
            expectancy=expectancy,
            profit_factor=profit_factor,
            max_consecutive_losses=_max_consecutive_losses(resolved_episodes),
            average_holding_sessions=_mean(
                [
                    Decimal(item.holding_sessions)
                    for item in resolved_episodes
                    if item.holding_sessions is not None
                ]
            ),
            total_fees=sum(
                (item.fees or Decimal("0") for item in resolved_episodes),
                Decimal("0"),
            ),
            total_slippage=(
                sum(
                    (
                        item.slippage
                        for item in resolved_episodes
                        if item.slippage is not None
                    ),
                    Decimal("0"),
                )
                if resolved_episodes
                and all(item.slippage is not None for item in resolved_episodes)
                else None
            ),
            average_episode_net_return=_mean(returns),
            average_episode_mfe=_mean(
                [item.mfe for item in resolved_episodes if item.mfe is not None]
            ),
            average_episode_mae=_mean(
                [item.mae for item in resolved_episodes if item.mae is not None]
            ),
            worst_episode_drawdown=(
                min(
                    item.episode_max_drawdown
                    for item in resolved_episodes
                    if item.episode_max_drawdown is not None
                )
                if any(
                    item.episode_max_drawdown is not None
                    for item in resolved_episodes
                )
                else None
            ),
            action_breakdown=tuple(action_breakdown),
            regime_breakdown=tuple(regime_breakdown),
            horizon_breakdown=tuple(horizon_breakdown),
            execution_attribution=execution_attribution,
            source_hash=source_hash,
        )
        if self.evaluations is not None:
            return self.evaluations.save(result)
        return result

    def _require_universe(self, experiment):
        snapshot = getattr(experiment, "universe_snapshot", None)
        if snapshot is None:
            if self.experiments is None:
                raise ValueError("experiment universe repository is required for strategy evaluation")
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


__all__ = ["StrategyEvaluationService"]

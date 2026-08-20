"""Read-only query composition for the N3 Lab HTTP boundary.

The service never resolves fresh outcomes, refreshes market data, or invokes
Formal Decision / Risk / execution code. It only projects already-persisted,
immutable experiment/evaluation facts into API-ready dictionaries.
"""
from __future__ import annotations

from collections import Counter

from app.domain.evaluation.common import OutcomeStatus


class LabQueryService:
    def __init__(
        self,
        experiment_repository,
        outcome_repository,
        strategy_evaluation_repository,
        benchmark_evaluation_repository,
    ) -> None:
        self.experiments = experiment_repository
        self.outcome_repository = outcome_repository
        self.strategy_evaluations = strategy_evaluation_repository
        self.benchmarks = benchmark_evaluation_repository

    @staticmethod
    def _value(value):
        return getattr(value, "value", value)

    def _experiment_item(self, experiment) -> dict[str, object]:
        return {
            "experiment_id": experiment.experiment_id,
            "experiment_version": experiment.experiment_version,
            "experiment_type": self._value(experiment.experiment_type),
            "status": self._value(experiment.status),
            "strategy_id": experiment.strategy_id,
            "strategy_version": experiment.strategy_version,
            "started_at": experiment.started_at,
            "ended_at": experiment.ended_at,
            "created_at": experiment.created_at,
            "universe_snapshot_id": experiment.universe_snapshot_id,
            "universe_snapshot_hash": experiment.universe_snapshot_hash,
            "universe_policy_version": experiment.universe_policy_version,
            "outcome_policy_version": experiment.outcome_policy_version,
            "benchmark_policy_version": experiment.benchmark_policy_version,
            "sample_quality_policy_version": experiment.sample_quality_policy_version,
            "evaluation_policy_version": experiment.evaluation_policy_version,
        }

    def list_experiments(
        self,
        *,
        strategy_id: str | None = None,
        experiment_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> dict[str, object]:
        rows = self.experiments.list(
            strategy_id=strategy_id,
            experiment_type=experiment_type,
            status=status,
            limit=limit,
        )
        items = tuple(self._experiment_item(row) for row in rows)
        return {"items": items, "count": len(items)}

    def resolve_experiment(self, experiment_id: str, version: str | None = None):
        normalized_id = str(experiment_id or "").strip()
        if not normalized_id:
            raise ValueError("experiment_id must not be blank")
        if version is not None:
            normalized_version = str(version).strip()
            if not normalized_version:
                raise ValueError("version must not be blank")
            experiment = self.experiments.get(normalized_id, normalized_version)
            selection_mode = "explicit_version"
        else:
            experiment = self.experiments.latest(normalized_id)
            selection_mode = "latest_version"
        if experiment is None:
            raise KeyError("experiment not found")
        return experiment, selection_mode

    def detail(self, experiment_id: str, version: str | None = None) -> dict[str, object]:
        experiment, selection_mode = self.resolve_experiment(experiment_id, version)
        universe = self.experiments.get_universe(experiment.universe_snapshot_id)
        if universe is None or universe.snapshot_hash != experiment.universe_snapshot_hash:
            raise ValueError("experiment universe lineage is unavailable or mismatched")
        return {
            "experiment": self._experiment_item(experiment),
            "selection_mode": selection_mode,
            "universe_member_count": len(universe.members),
            "universe_members": tuple(
                {"market": member.market, "symbol": member.symbol}
                for member in universe.members
            ),
            "definition_hash": experiment.definition_hash,
        }

    @staticmethod
    def _count_status(rows) -> dict[str, int]:
        counts = Counter(str(getattr(item.outcome_status, "value", item.outcome_status)) for item in rows)
        return {
            "terminal": len(rows),
            "resolved": counts.get(OutcomeStatus.RESOLVED.value, 0),
            "insufficient": counts.get(OutcomeStatus.INSUFFICIENT_DATA.value, 0),
            "invalid": counts.get(OutcomeStatus.INVALID.value, 0),
        }

    def _outcome_rows(self, experiment):
        identity = (experiment.experiment_id, experiment.experiment_version)
        return (
            self.outcome_repository.list_decisions(*identity),
            self.outcome_repository.list_executions(*identity),
            self.outcome_repository.list_episodes(*identity),
        )

    def _outcome_counts(self, experiment) -> dict[str, object]:
        decisions, executions, episodes = self._outcome_rows(experiment)
        decision_counts = self._count_status(decisions)
        execution_counts = self._count_status(executions)
        episode_counts = self._count_status(episodes)
        return {
            "decision_terminal_count": decision_counts["terminal"],
            "decision_resolved_count": decision_counts["resolved"],
            "decision_insufficient_count": decision_counts["insufficient"],
            "decision_invalid_count": decision_counts["invalid"],
            "execution_terminal_count": execution_counts["terminal"],
            "execution_resolved_count": execution_counts["resolved"],
            "execution_insufficient_count": execution_counts["insufficient"],
            "execution_invalid_count": execution_counts["invalid"],
            "episode_terminal_count": episode_counts["terminal"],
            "episode_resolved_count": episode_counts["resolved"],
            "episode_insufficient_count": episode_counts["insufficient"],
            "episode_invalid_count": episode_counts["invalid"],
            "pending_decision_count": None,
            "pending_count_reason": "pending_outcomes_are_derived_not_materialized_n3_6",
        }

    def _strategy_summary(self, experiment) -> dict[str, object]:
        evaluation = self.strategy_evaluations.latest(
            experiment.experiment_id,
            experiment.experiment_version,
        )
        if evaluation is None:
            return {
                "available": False,
                "reason_codes": ("strategy_evaluation_not_materialized",),
            }
        return {
            "available": True,
            "evaluation_id": evaluation.evaluation_id,
            "computed_at": evaluation.computed_at,
            "sample_quality": self._value(evaluation.sample_quality),
            "resolved_decision_count": evaluation.resolved_decision_count,
            "completed_trade_count": evaluation.completed_trade_count,
            "distinct_symbol_count": evaluation.distinct_symbol_count,
            "reason_codes": (),
        }

    def _benchmark_summary(self, experiment) -> dict[str, object]:
        evaluation = self.benchmarks.latest_evaluation(
            experiment.experiment_id,
            experiment.experiment_version,
        )
        if evaluation is None:
            return {
                "available": False,
                "reason_codes": ("benchmark_evaluation_not_materialized",),
            }
        return {
            "available": True,
            "benchmark_evaluation_id": evaluation.benchmark_evaluation_id,
            "benchmark_policy_id": evaluation.benchmark_policy_id,
            "benchmark_policy_version": evaluation.benchmark_policy_version,
            "benchmark_type": self._value(evaluation.benchmark_type),
            "computed_at": evaluation.computed_at,
            "resolved_observation_count": evaluation.resolved_observation_count,
            "nonresolved_observation_count": evaluation.nonresolved_observation_count,
            "reason_codes": (),
        }

    def summary(self, experiment_id: str, version: str | None = None) -> dict[str, object]:
        experiment, _ = self.resolve_experiment(experiment_id, version)
        return {
            "experiment": self._experiment_item(experiment),
            "outcome_counts": self._outcome_counts(experiment),
            "strategy": self._strategy_summary(experiment),
            "benchmark": self._benchmark_summary(experiment),
        }

    def outcomes(
        self,
        experiment_id: str,
        version: str | None = None,
        *,
        limit: int = 200,
    ) -> dict[str, object]:
        experiment, _ = self.resolve_experiment(experiment_id, version)
        decisions, executions, episodes = self._outcome_rows(experiment)
        limited_decisions = decisions[:limit]
        limited_executions = executions[:limit]
        limited_episodes = episodes[:limit]
        return {
            "experiment_id": experiment.experiment_id,
            "experiment_version": experiment.experiment_version,
            "terminal_only": True,
            "pending_materialized": False,
            "pending_reason": "pending_outcomes_are_derived_not_materialized_n3_6",
            "decision_outcomes": tuple(
                {
                    "outcome_id": row.outcome_id,
                    "decision_id": row.decision_id,
                    "symbol": row.symbol,
                    "market": row.market,
                    "action": self._value(row.action),
                    "horizon_sessions": row.horizon_sessions,
                    "outcome_status": self._value(row.outcome_status),
                    "decision_time": row.decision_time,
                    "observation_end": row.observation_end,
                    "forward_return": row.forward_return,
                    "mfe": row.mfe,
                    "mae": row.mae,
                    "market_regime": row.market_regime,
                    "action_outcome_class": self._value(row.action_outcome_class) if row.action_outcome_class is not None else None,
                    "outcome_reason_codes": tuple(row.outcome_reason_codes),
                    "resolved_at": row.resolved_at,
                }
                for row in limited_decisions
            ),
            "execution_outcomes": tuple(
                {
                    "execution_outcome_id": row.execution_outcome_id,
                    "decision_id": row.decision_id,
                    "requested_action": self._value(row.requested_action),
                    "outcome_status": self._value(row.outcome_status),
                    "execution_disposition": self._value(row.execution_disposition),
                    "requested_quantity": row.requested_quantity,
                    "max_executable_quantity": row.max_executable_quantity,
                    "executed_quantity": row.executed_quantity,
                    "deferral_id": row.deferral_id,
                    "fill_count": len(row.fill_ids),
                    "execution_reason_codes": tuple(row.execution_reason_codes),
                    "resolved_at": row.resolved_at,
                }
                for row in limited_executions
            ),
            "trade_episode_outcomes": tuple(
                {
                    "episode_outcome_id": row.episode_outcome_id,
                    "position_episode_id": row.position_episode_id,
                    "symbol": row.symbol,
                    "outcome_status": self._value(row.outcome_status),
                    "opened_at": row.opened_at,
                    "closed_at": row.closed_at,
                    "holding_sessions": row.holding_sessions,
                    "net_return": row.net_return,
                    "realized_pnl": row.realized_pnl,
                    "fees": row.fees,
                    "slippage": row.slippage,
                    "mfe": row.mfe,
                    "mae": row.mae,
                    "episode_max_drawdown": row.episode_max_drawdown,
                    "outcome_reason_codes": tuple(row.outcome_reason_codes),
                    "resolved_at": row.resolved_at,
                }
                for row in limited_episodes
            ),
        }

    def performance(self, experiment_id: str, version: str | None = None) -> dict[str, object]:
        experiment, _ = self.resolve_experiment(experiment_id, version)
        strategy = self.strategy_evaluations.latest(experiment.experiment_id, experiment.experiment_version)
        benchmark = self.benchmarks.latest_evaluation(experiment.experiment_id, experiment.experiment_version)
        if strategy is None:
            strategy_payload = {
                "available": False,
                "reason_codes": ("strategy_evaluation_not_materialized",),
            }
        else:
            strategy_payload = {
                "available": True,
                "evaluation_id": strategy.evaluation_id,
                "computed_at": strategy.computed_at,
                "sample_quality": self._value(strategy.sample_quality),
                "resolved_decision_count": strategy.resolved_decision_count,
                "completed_trade_count": strategy.completed_trade_count,
                "distinct_symbol_count": strategy.distinct_symbol_count,
                "total_return": strategy.total_return,
                "max_drawdown": strategy.max_drawdown,
                "turnover": strategy.turnover,
                "win_rate": strategy.win_rate,
                "average_win": strategy.average_win,
                "average_loss": strategy.average_loss,
                "payoff_ratio": strategy.payoff_ratio,
                "expectancy": strategy.expectancy,
                "profit_factor": strategy.profit_factor,
                "max_consecutive_losses": strategy.max_consecutive_losses,
                "average_holding_sessions": strategy.average_holding_sessions,
                "total_fees": strategy.total_fees,
                "total_slippage": strategy.total_slippage,
                "average_episode_net_return": strategy.average_episode_net_return,
                "worst_episode_drawdown": strategy.worst_episode_drawdown,
                "reason_codes": tuple(strategy.portfolio_metric_reason_codes),
            }
        if benchmark is None:
            benchmark_payload = {
                "available": False,
                "reason_codes": ("benchmark_evaluation_not_materialized",),
            }
        else:
            benchmark_payload = {
                "available": True,
                "benchmark_evaluation_id": benchmark.benchmark_evaluation_id,
                "benchmark_policy_id": benchmark.benchmark_policy_id,
                "benchmark_policy_version": benchmark.benchmark_policy_version,
                "benchmark_type": self._value(benchmark.benchmark_type),
                "computed_at": benchmark.computed_at,
                "resolved_observation_count": benchmark.resolved_observation_count,
                "nonresolved_observation_count": benchmark.nonresolved_observation_count,
                "mean_strategy_forward_return": benchmark.mean_strategy_forward_return,
                "mean_benchmark_forward_return": benchmark.mean_benchmark_forward_return,
                "mean_excess_forward_return": benchmark.mean_excess_forward_return,
                "portfolio_benchmark_return": benchmark.portfolio_benchmark_return,
                "portfolio_excess_return": benchmark.portfolio_excess_return,
                "reason_codes": tuple(benchmark.portfolio_metric_reason_codes),
            }
        return {
            "experiment": self._experiment_item(experiment),
            "strategy": strategy_payload,
            "benchmark": benchmark_payload,
        }

    def breakdown(self, experiment_id: str, version: str | None = None) -> dict[str, object]:
        experiment, _ = self.resolve_experiment(experiment_id, version)
        strategy = self.strategy_evaluations.latest(experiment.experiment_id, experiment.experiment_version)
        benchmark = self.benchmarks.latest_evaluation(experiment.experiment_id, experiment.experiment_version)
        reasons: list[str] = []
        if strategy is None:
            reasons.append("strategy_evaluation_not_materialized")
        if benchmark is None:
            reasons.append("benchmark_evaluation_not_materialized")

        def decision_breakdown(items):
            return tuple(
                {
                    "action": self._value(item.action) if item.action is not None else None,
                    "market_regime": item.market_regime,
                    "horizon_sessions": item.horizon_sessions,
                    "sample_count": item.sample_count,
                    "favorable_count": item.favorable_count,
                    "unfavorable_count": item.unfavorable_count,
                    "mixed_count": item.mixed_count,
                    "neutral_count": item.neutral_count,
                    "not_applicable_count": item.not_applicable_count,
                    "mean_forward_return": item.mean_forward_return,
                    "mean_mfe": item.mean_mfe,
                    "mean_mae": item.mean_mae,
                }
                for item in items
            )

        return {
            "experiment": self._experiment_item(experiment),
            "action_breakdown": decision_breakdown(strategy.action_breakdown) if strategy else (),
            "regime_breakdown": decision_breakdown(strategy.regime_breakdown) if strategy else (),
            "horizon_breakdown": decision_breakdown(strategy.horizon_breakdown) if strategy else (),
            "execution_attribution": tuple(
                {
                    "disposition": self._value(item.disposition),
                    "count": item.count,
                    "resolved_count": item.resolved_count,
                    "nonresolved_count": item.nonresolved_count,
                }
                for item in (strategy.execution_attribution if strategy else ())
            ),
            "benchmark_horizon_breakdown": tuple(
                {
                    "market": item.market,
                    "horizon_sessions": item.horizon_sessions,
                    "resolved_count": item.resolved_count,
                    "nonresolved_count": item.nonresolved_count,
                    "mean_strategy_forward_return": item.mean_strategy_forward_return,
                    "mean_benchmark_forward_return": item.mean_benchmark_forward_return,
                    "mean_excess_forward_return": item.mean_excess_forward_return,
                }
                for item in (benchmark.horizon_breakdown if benchmark else ())
            ),
            "reason_codes": tuple(reasons),
        }

    def compare(self, selectors: tuple[str, ...]) -> dict[str, object]:
        if len(selectors) < 2:
            raise ValueError("compare requires at least two experiment selectors")
        if len(selectors) > 8:
            raise ValueError("compare supports at most eight experiment selectors")
        rows: list[dict[str, object]] = []
        for selector in selectors:
            raw = str(selector or "").strip()
            if not raw:
                raise ValueError("compare selectors must not be blank")
            experiment_id, separator, version = raw.partition("@")
            experiment, _ = self.resolve_experiment(
                experiment_id,
                version if separator else None,
            )
            strategy = self.strategy_evaluations.latest(experiment.experiment_id, experiment.experiment_version)
            benchmark = self.benchmarks.latest_evaluation(experiment.experiment_id, experiment.experiment_version)
            reasons: list[str] = []
            if strategy is None:
                reasons.append("strategy_evaluation_not_materialized")
            if benchmark is None:
                reasons.append("benchmark_evaluation_not_materialized")
            rows.append({
                "experiment": self._experiment_item(experiment),
                "sample_quality": self._value(strategy.sample_quality) if strategy else None,
                "resolved_decision_count": strategy.resolved_decision_count if strategy else None,
                "completed_trade_count": strategy.completed_trade_count if strategy else None,
                "win_rate": strategy.win_rate if strategy else None,
                "expectancy": strategy.expectancy if strategy else None,
                "profit_factor": strategy.profit_factor if strategy else None,
                "average_episode_net_return": strategy.average_episode_net_return if strategy else None,
                "mean_benchmark_forward_return": benchmark.mean_benchmark_forward_return if benchmark else None,
                "mean_excess_forward_return": benchmark.mean_excess_forward_return if benchmark else None,
                "strategy_available": strategy is not None,
                "benchmark_available": benchmark is not None,
                "reason_codes": tuple(reasons),
            })
        return {"selectors": selectors, "rows": tuple(rows)}


__all__ = ["LabQueryService"]

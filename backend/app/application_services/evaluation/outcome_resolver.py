"""Deterministic, local-only N3 outcome resolution.

OutcomeResolver turns immutable experiment/decision lineage plus already-persisted
market/execution facts into N3 outcome contracts. It deliberately has no
provider client and never refreshes market data: missing local evidence remains
PENDING or INSUFFICIENT_DATA instead of becoming a hidden remote lookup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Mapping

from app.decision_semantics import FormalDecisionAction, formal_action_from_report
from app.domain.evaluation import (
    ActionOutcomeClass,
    DecisionOutcome,
    ExecutionDisposition,
    ExecutionOutcome,
    OutcomePolicy,
    OutcomeStatus,
    TradeEpisodeOutcome,
    swing_v1_outcome_policy,
)
from app.market_adapter import market_for_symbol
from app.time_utils import beijing_now
from app.trading_calendar import TradingCalendarService


@dataclass(frozen=True)
class DecisionResolution:
    decision_outcomes: tuple[DecisionOutcome, ...]
    execution_outcome: ExecutionOutcome


def _aware_datetime(value: object, *, label: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")
    return result


def _decimal(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _market_code(raw: object, symbol: str) -> str | None:
    normalized = str(raw or "").strip().upper()
    aliases = {"CN_A": "CN", "A": "CN", "MAINLAND": "CN"}
    normalized = aliases.get(normalized, normalized)
    if normalized in {"CN", "HK", "US"}:
        return normalized
    return market_for_symbol(symbol)


def _finite_ohlc(bar: Mapping[str, object]) -> bool:
    values = [_decimal(bar.get(field)) for field in ("open", "close", "high", "low")]
    return all(value is not None and value > 0 for value in values)


def _classify(action: FormalDecisionAction, forward_return: Decimal) -> ActionOutcomeClass:
    if action == "BLOCKED":
        return ActionOutcomeClass.NOT_APPLICABLE
    if forward_return == 0:
        return ActionOutcomeClass.NEUTRAL
    benefits_from_upside = action in {"BUY", "ADD", "HOLD"}
    favorable = forward_return > 0 if benefits_from_upside else forward_return < 0
    return ActionOutcomeClass.FAVORABLE if favorable else ActionOutcomeClass.UNFAVORABLE


class OutcomeResolver:
    """Resolve outcomes from persisted facts only, with no provider I/O."""

    def __init__(
        self,
        source_repository,
        *,
        outcome_repository=None,
        experiment_repository=None,
        trading_calendar: TradingCalendarService | None = None,
        outcome_policy: OutcomePolicy | None = None,
    ) -> None:
        self.source = source_repository
        self.outcomes = outcome_repository
        self.experiments = experiment_repository
        self.calendar = trading_calendar or TradingCalendarService()
        self.policy = outcome_policy or swing_v1_outcome_policy()

    def resolve_decision(
        self,
        experiment,
        decision_id: str,
        *,
        as_of: datetime | None = None,
    ) -> DecisionResolution:
        self._require_policy(experiment)
        resolved_at = self._normalize_as_of(as_of)
        bundle = self.source.decision_bundle(decision_id)
        if not bundle:
            raise ValueError("evaluation decision source not found")
        report = bundle.get("report") if isinstance(bundle, Mapping) else None
        context = bundle.get("context") if isinstance(bundle, Mapping) else None
        if not isinstance(report, Mapping) or not isinstance(context, Mapping):
            raise ValueError("evaluation decision source is incomplete")

        action = formal_action_from_report(report)
        symbol = str(report.get("symbol") or context.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("evaluation decision symbol is missing")
        decision_time = _aware_datetime(report.get("generated_at"), label="decision generated_at")
        instrument = context.get("instrument") if isinstance(context.get("instrument"), Mapping) else {}
        market = _market_code(instrument.get("market"), symbol)
        if market is None:
            raise ValueError("evaluation market cannot be resolved")
        self._require_universe_member(experiment, symbol, market)
        reference_price = self._reference_price(report, context)
        market_regime = self._market_regime(context)

        decision_outcomes = tuple(
            self._resolve_horizon(
                experiment=experiment,
                report=report,
                symbol=symbol,
                market=market,
                action=action,
                decision_time=decision_time,
                reference_price=reference_price,
                market_regime=market_regime,
                horizon=horizon,
                as_of=resolved_at,
            )
            for horizon in self.policy.decision_horizons
        )
        execution = self._resolve_execution(
            experiment=experiment,
            report=report,
            action=action,
            as_of=resolved_at,
        )
        return DecisionResolution(decision_outcomes=decision_outcomes, execution_outcome=execution)

    def resolve_episode(
        self,
        experiment,
        position_episode_id: str,
        *,
        as_of: datetime | None = None,
    ) -> TradeEpisodeOutcome:
        self._require_policy(experiment)
        terminal_id = (
            f"{experiment.experiment_id}:{experiment.experiment_version}:episode:{position_episode_id}"
        )
        existing = self._get_existing("episode", terminal_id)
        if existing is not None:
            return existing

        now = self._normalize_as_of(as_of)
        episode = self.source.position_episode(position_episode_id)
        if not isinstance(episode, Mapping):
            raise ValueError("paper position episode not found")
        symbol = str(episode.get("symbol") or "").strip().upper()
        opened_at = _aware_datetime(episode.get("opened_at"), label="episode opened_at")
        closed_raw = episode.get("closed_at")
        if not closed_raw:
            return TradeEpisodeOutcome(
                episode_outcome_id=terminal_id,
                experiment_id=experiment.experiment_id,
                experiment_version=experiment.experiment_version,
                position_episode_id=position_episode_id,
                symbol=symbol,
                outcome_status=OutcomeStatus.PENDING,
                opened_at=opened_at,
                outcome_policy_version=self.policy.version,
            )
        closed_at = _aware_datetime(closed_raw, label="episode closed_at")
        if now < closed_at:
            raise ValueError("episode resolution as_of precedes closed_at")

        fills = tuple(self.source.fills_for_episode(symbol, opened_at, closed_at))
        lineage_base = {
            "episode": dict(episode),
            "fills": [dict(item) for item in fills],
            "universe_snapshot_hash": experiment.universe_snapshot_hash,
        }
        if not fills:
            return self._terminal_episode_insufficient(
                experiment,
                terminal_id,
                position_episode_id,
                symbol,
                opened_at,
                closed_at,
                now,
                lineage_base,
                "episode_fill_lineage_missing",
            )

        parsed = []
        for fill in fills:
            side = str(fill.get("side") or "").upper()
            qty = _decimal(fill.get("quantity"))
            price = _decimal(fill.get("price"))
            fee = _decimal(fill.get("fee")) or Decimal("0")
            if side not in {"BUY", "SELL"} or qty is None or qty <= 0 or price is None or price <= 0:
                return self._terminal_episode_insufficient(
                    experiment,
                    terminal_id,
                    position_episode_id,
                    symbol,
                    opened_at,
                    closed_at,
                    now,
                    lineage_base,
                    "episode_fill_invalid",
                )
            parsed.append((fill, side, qty, price, fee))

        buy_qty = sum((qty for _, side, qty, _, _ in parsed if side == "BUY"), Decimal("0"))
        sell_qty = sum((qty for _, side, qty, _, _ in parsed if side == "SELL"), Decimal("0"))
        if buy_qty <= 0 or sell_qty <= 0 or abs(buy_qty - sell_qty) > Decimal("0.000001"):
            return self._terminal_episode_insufficient(
                experiment,
                terminal_id,
                position_episode_id,
                symbol,
                opened_at,
                closed_at,
                now,
                lineage_base,
                "episode_not_fully_closed_by_fill_lineage",
            )

        buy_notional = sum(
            (qty * price for _, side, qty, price, _ in parsed if side == "BUY"),
            Decimal("0"),
        )
        sell_notional = sum(
            (qty * price for _, side, qty, price, _ in parsed if side == "SELL"),
            Decimal("0"),
        )
        fees = sum((fee for _, _, _, _, fee in parsed), Decimal("0"))
        if buy_notional <= 0:
            return self._terminal_episode_insufficient(
                experiment,
                terminal_id,
                position_episode_id,
                symbol,
                opened_at,
                closed_at,
                now,
                lineage_base,
                "episode_cost_basis_missing",
            )

        if not all(
            str(fill.get("fill_price_mode") or "") == "NEXT_ELIGIBLE_OBSERVED_QUOTE"
            and bool(str(fill.get("execution_quote_at") or "").strip())
            for fill, *_ in parsed
        ):
            return self._terminal_episode_insufficient(
                experiment,
                terminal_id,
                position_episode_id,
                symbol,
                opened_at,
                closed_at,
                now,
                lineage_base,
                "slippage_reference_unavailable",
            )

        entry_price = _decimal(episode.get("entry_price"))
        if entry_price is None or entry_price <= 0:
            return self._terminal_episode_insufficient(
                experiment,
                terminal_id,
                position_episode_id,
                symbol,
                opened_at,
                closed_at,
                now,
                lineage_base,
                "episode_entry_price_missing",
            )

        market = market_for_symbol(symbol)
        if market is None:
            return self._terminal_episode_insufficient(
                experiment,
                terminal_id,
                position_episode_id,
                symbol,
                opened_at,
                closed_at,
                now,
                lineage_base,
                "episode_market_unknown",
            )
        self._require_universe_member(experiment, symbol, market)

        # Daily OHLC cannot safely describe the partial opening/closing session
        # around intraday fills. Use only full sessions strictly between the
        # boundaries and the actual fill prices at each endpoint.
        first_full = opened_at.date() + timedelta(days=1)
        last_full = closed_at.date() - timedelta(days=1)
        bars: tuple[Mapping[str, object], ...] = ()
        if first_full <= last_full:
            bars = tuple(
                self.source.daily_bars_between(
                    symbol,
                    first_full.isoformat(),
                    last_full.isoformat(),
                )
            )
            if any(not self._bar_is_eligible(bar) for bar in bars):
                lineage_base["bars"] = [dict(item) for item in bars]
                return self._terminal_episode_insufficient(
                    experiment,
                    terminal_id,
                    position_episode_id,
                    symbol,
                    opened_at,
                    closed_at,
                    now,
                    lineage_base,
                    "episode_market_path_invalid",
                )

        average_exit = sell_notional / sell_qty
        highs = [entry_price, average_exit]
        lows = [entry_price, average_exit]
        closes = [entry_price]
        for bar in bars:
            highs.append(_decimal(bar.get("high")) or entry_price)
            lows.append(_decimal(bar.get("low")) or entry_price)
            closes.append(_decimal(bar.get("close")) or entry_price)
        closes.append(average_exit)
        mfe = max((price / entry_price - 1 for price in highs), default=Decimal("0"))
        mae = min((price / entry_price - 1 for price in lows), default=Decimal("0"))
        mfe = max(Decimal("0"), mfe)
        mae = min(Decimal("0"), mae)
        drawdown = self._max_drawdown(closes)

        session_dates = self.calendar.session_dates(
            market,
            opened_at.date().isoformat(),
            closed_at.date().isoformat(),
        )
        gross_pnl = sell_notional - buy_notional
        net_pnl = gross_pnl - fees
        gross_return = gross_pnl / buy_notional
        net_return = net_pnl / buy_notional

        entry_decision_ids: list[str] = []
        position_decision_ids: list[str] = []
        for fill, *_ in parsed:
            fill_decision_id = str(fill.get("decision_id") or "").strip()
            if not fill_decision_id:
                continue
            fill_report = self.source.decision_report(fill_decision_id)
            fill_action = (
                formal_action_from_report(fill_report)
                if isinstance(fill_report, Mapping)
                else None
            )
            target = entry_decision_ids if fill_action == "BUY" else position_decision_ids
            if fill_decision_id not in target:
                target.append(fill_decision_id)

        lineage_base["bars"] = [dict(item) for item in bars]
        source_hash = _canonical_hash(lineage_base)
        outcome = TradeEpisodeOutcome(
            episode_outcome_id=terminal_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            position_episode_id=position_episode_id,
            symbol=symbol,
            outcome_status=OutcomeStatus.RESOLVED,
            opened_at=opened_at,
            closed_at=closed_at,
            holding_sessions=len(session_dates),
            gross_return=gross_return,
            net_return=net_return,
            realized_pnl=net_pnl,
            fees=fees,
            slippage=Decimal("0"),
            mfe=mfe,
            mae=mae,
            episode_max_drawdown=drawdown,
            entry_decision_ids=tuple(entry_decision_ids),
            position_decision_ids=tuple(position_decision_ids),
            fill_ids=tuple(str(fill.get("id")) for fill, *_ in parsed),
            outcome_policy_version=self.policy.version,
            source_lineage_hash=source_hash,
            resolved_at=now,
        )
        return self._save_terminal("episode", outcome)

    def _resolve_horizon(
        self,
        *,
        experiment,
        report: Mapping[str, object],
        symbol: str,
        market: str,
        action: FormalDecisionAction,
        decision_time: datetime,
        reference_price: Decimal | None,
        market_regime: str | None,
        horizon: int,
        as_of: datetime,
    ) -> DecisionOutcome:
        outcome_id = (
            f"{experiment.experiment_id}:{experiment.experiment_version}:"
            f"{report['decision_id']}:h{horizon}"
        )
        existing = self._get_existing("decision", outcome_id)
        if existing is not None:
            return existing

        anchor = self.calendar.latest_session_date(market, decision_time)
        if anchor is None:
            return self._terminal_decision_nonresolved(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                reference_price,
                horizon,
                decision_time,
                market_regime,
                as_of,
                OutcomeStatus.INVALID,
                ("market_calendar_anchor_unavailable",),
                {"decision": dict(report)},
            )

        projected_dates = self._future_market_sessions(market, anchor, horizon)
        if len(projected_dates) < horizon:
            return self._terminal_decision_nonresolved(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                reference_price,
                horizon,
                decision_time,
                market_regime,
                as_of,
                OutcomeStatus.INVALID,
                ("market_calendar_window_unavailable",),
                {"decision": dict(report), "anchor": anchor},
            )
        projected_end = self.calendar.session_close(market, projected_dates[-1]) or decision_time

        if reference_price is None or reference_price <= 0:
            # Missing reference price is already a terminal source-quality
            # failure; do not wait for a future horizon or fabricate a price.
            return self._terminal_decision_nonresolved(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                None,
                horizon,
                decision_time,
                market_regime,
                as_of,
                OutcomeStatus.INSUFFICIENT_DATA,
                ("reference_price_unavailable",),
                {"decision": dict(report)},
            )

        latest_completed = self.calendar.latest_completed_session_date(market, as_of)
        if latest_completed is None or latest_completed <= anchor:
            return self._pending_decision(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                reference_price,
                horizon,
                projected_end,
                market_regime,
                ("observation_window_open",),
            )

        start_date = (date.fromisoformat(anchor) + timedelta(days=1)).isoformat()
        bars = tuple(self.source.daily_bars_between(symbol, start_date, latest_completed))
        bars_by_date = {str(bar.get("trading_date")): bar for bar in bars}
        completed_sessions = self.calendar.session_dates(market, start_date, latest_completed)
        observable: list[Mapping[str, object]] = []
        for session in completed_sessions:
            raw = bars_by_date.get(session)
            if raw is None:
                # No bar is treated as non-observable (for example a suspension)
                # under swing-v1-outcome v1; it is not silently fabricated.
                continue
            if not self._bar_is_eligible(raw):
                actual_end = self.calendar.session_close(market, session) or projected_end
                return self._terminal_decision_nonresolved(
                    experiment,
                    outcome_id,
                    report,
                    symbol,
                    market,
                    action,
                    decision_time,
                    reference_price,
                    horizon,
                    actual_end,
                    market_regime,
                    as_of,
                    OutcomeStatus.INSUFFICIENT_DATA,
                    ("market_bar_invalid_or_adjustment_mismatch",),
                    {"decision": dict(report), "bar": dict(raw), "anchor": anchor},
                )
            observable.append(raw)
            if len(observable) == horizon:
                break

        if len(observable) < horizon:
            return self._pending_decision(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                reference_price,
                horizon,
                projected_end,
                market_regime,
                ("observation_incomplete_or_suspended",),
            )

        terminal_date = str(observable[-1]["trading_date"])
        observation_end = self.calendar.session_close(market, terminal_date) or projected_end
        if as_of < observation_end:
            return self._pending_decision(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                reference_price,
                horizon,
                observation_end,
                market_regime,
                ("observation_window_open",),
            )

        close = _decimal(observable[-1].get("close"))
        highs = [_decimal(bar.get("high")) for bar in observable]
        lows = [_decimal(bar.get("low")) for bar in observable]
        if close is None or any(value is None for value in highs + lows):
            return self._terminal_decision_nonresolved(
                experiment,
                outcome_id,
                report,
                symbol,
                market,
                action,
                decision_time,
                reference_price,
                horizon,
                observation_end,
                market_regime,
                as_of,
                OutcomeStatus.INSUFFICIENT_DATA,
                ("market_bar_numeric_value_missing",),
                {"decision": dict(report), "bars": [dict(item) for item in observable]},
            )
        forward_return = close / reference_price - 1
        mfe = max(
            Decimal("0"),
            max(value / reference_price - 1 for value in highs if value is not None),
        )
        mae = min(
            Decimal("0"),
            min(value / reference_price - 1 for value in lows if value is not None),
        )

        target_rule = next(
            (
                rule
                for rule in self.policy.target_stop_rules
                if rule.action == action and rule.horizon_sessions == horizon
            ),
            None,
        )
        target_hit = stop_hit = target_before_stop = None
        reason_codes: list[str] = []
        if target_rule is not None:
            target_hit, stop_hit, target_before_stop, ambiguous = self._target_stop_facts(
                observable,
                reference_price,
                target_rule.target_return,
                target_rule.stop_return,
            )
            if ambiguous:
                reason_codes.append("target_stop_same_session_order_unknown")

        lineage = {
            "decision_id": report.get("decision_id"),
            "decision_input_hash": report.get("input_hash"),
            "anchor_session": anchor,
            "bars": [dict(item) for item in observable],
            "outcome_policy_hash": self.policy.contract_hash,
            "universe_snapshot_hash": experiment.universe_snapshot_hash,
        }
        outcome = DecisionOutcome(
            outcome_id=outcome_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            decision_id=str(report["decision_id"]),
            symbol=symbol,
            market=market,
            action=action,
            decision_time=decision_time,
            reference_price=reference_price,
            horizon_sessions=horizon,
            observation_end=observation_end,
            outcome_status=OutcomeStatus.RESOLVED,
            forward_return=forward_return,
            mfe=mfe,
            mae=mae,
            target_hit=target_hit,
            stop_hit=stop_hit,
            target_before_stop=target_before_stop,
            market_regime=market_regime,
            action_outcome_class=_classify(action, forward_return),
            outcome_reason_codes=tuple(reason_codes),
            source_lineage_hash=_canonical_hash(lineage),
            outcome_policy_version=self.policy.version,
            resolved_at=as_of,
        )
        return self._save_terminal("decision", outcome)

    def _resolve_execution(
        self,
        *,
        experiment,
        report: Mapping[str, object],
        action: FormalDecisionAction,
        as_of: datetime,
    ) -> ExecutionOutcome:
        decision_id = str(report["decision_id"])
        outcome_id = (
            f"{experiment.experiment_id}:{experiment.experiment_version}:"
            f"{decision_id}:execution"
        )
        existing = self._get_existing("execution", outcome_id)
        if existing is not None:
            return existing

        fills = tuple(self.source.fills_for_decision(decision_id))
        deferral = self.source.deferral_for_decision(decision_id)
        sizing = report.get("sizing") if isinstance(report.get("sizing"), Mapping) else {}
        requested = _decimal(sizing.get("suggested_quantity"))
        maximum = _decimal(sizing.get("max_executable_quantity"))
        lineage = {
            "decision_id": decision_id,
            "input_hash": report.get("input_hash"),
            "sizing": dict(sizing),
            "fills": [dict(item) for item in fills],
            "deferral": dict(deferral) if isinstance(deferral, Mapping) else None,
            "universe_snapshot_hash": experiment.universe_snapshot_hash,
        }
        lineage_hash = _canonical_hash(lineage)

        if action in {"WAIT", "HOLD", "BLOCKED"}:
            result = ExecutionOutcome(
                execution_outcome_id=outcome_id,
                experiment_id=experiment.experiment_id,
                experiment_version=experiment.experiment_version,
                decision_id=decision_id,
                requested_action=action,
                outcome_status=OutcomeStatus.RESOLVED,
                execution_disposition=ExecutionDisposition.NOT_APPLICABLE,
                resolved_at=as_of,
                source_lineage_hash=lineage_hash,
            )
            return self._save_terminal("execution", result)

        if fills:
            quantities = [_decimal(fill.get("quantity")) for fill in fills]
            if any(value is None or value <= 0 for value in quantities):
                return self._execution_insufficient(
                    experiment,
                    outcome_id,
                    decision_id,
                    action,
                    requested,
                    maximum,
                    as_of,
                    lineage_hash,
                    "execution_fill_quantity_invalid",
                )
            executed = sum(
                (value for value in quantities if value is not None),
                Decimal("0"),
            )
            if requested is not None and executed > requested + Decimal("0.000001"):
                return self._execution_insufficient(
                    experiment,
                    outcome_id,
                    decision_id,
                    action,
                    requested,
                    maximum,
                    as_of,
                    lineage_hash,
                    "execution_quantity_exceeds_request",
                )
            if maximum is not None and executed > maximum + Decimal("0.000001"):
                return self._execution_insufficient(
                    experiment,
                    outcome_id,
                    decision_id,
                    action,
                    requested,
                    maximum,
                    as_of,
                    lineage_hash,
                    "execution_quantity_exceeds_maximum",
                )
            disposition = (
                ExecutionDisposition.PARTIALLY_EXECUTED
                if requested is not None and executed + Decimal("0.000001") < requested
                else ExecutionDisposition.EXECUTED
            )
            observed_quote_at = None
            for fill in reversed(fills):
                raw = fill.get("execution_quote_at") or fill.get("executed_at")
                if raw:
                    try:
                        observed_quote_at = _aware_datetime(
                            raw,
                            label="execution quote time",
                        )
                        break
                    except ValueError:
                        continue
            result = ExecutionOutcome(
                execution_outcome_id=outcome_id,
                experiment_id=experiment.experiment_id,
                experiment_version=experiment.experiment_version,
                decision_id=decision_id,
                requested_action=action,
                outcome_status=OutcomeStatus.RESOLVED,
                execution_disposition=disposition,
                requested_quantity=requested,
                max_executable_quantity=maximum,
                executed_quantity=executed,
                observed_quote_at=observed_quote_at,
                market_session_status="EXECUTED_AUDIT",
                fill_ids=tuple(str(fill.get("id")) for fill in fills),
                resolved_at=as_of,
                source_lineage_hash=lineage_hash,
            )
            return self._save_terminal("execution", result)

        if isinstance(deferral, Mapping):
            state = str(deferral.get("state") or "").strip().lower()
            reason = str(
                deferral.get("reason_code") or "execution_deferred"
            ).strip()
            if state == "active":
                result = ExecutionOutcome(
                    execution_outcome_id=outcome_id,
                    experiment_id=experiment.experiment_id,
                    experiment_version=experiment.experiment_version,
                    decision_id=decision_id,
                    requested_action=action,
                    outcome_status=OutcomeStatus.RESOLVED,
                    execution_disposition=ExecutionDisposition.DEFERRED,
                    execution_reason_codes=(reason,),
                    requested_quantity=requested,
                    max_executable_quantity=maximum,
                    executed_quantity=Decimal("0"),
                    deferral_id=decision_id,
                    resolved_at=as_of,
                    source_lineage_hash=lineage_hash,
                )
                return self._save_terminal("execution", result)
            if state == "superseded":
                result = ExecutionOutcome(
                    execution_outcome_id=outcome_id,
                    experiment_id=experiment.experiment_id,
                    experiment_version=experiment.experiment_version,
                    decision_id=decision_id,
                    requested_action=action,
                    outcome_status=OutcomeStatus.RESOLVED,
                    execution_disposition=ExecutionDisposition.EXPIRED,
                    execution_reason_codes=(reason, "execution_deferral_superseded"),
                    requested_quantity=requested,
                    max_executable_quantity=maximum,
                    executed_quantity=Decimal("0"),
                    resolved_at=as_of,
                    source_lineage_hash=lineage_hash,
                )
                return self._save_terminal("execution", result)
            if state == "released":
                return self._execution_insufficient(
                    experiment,
                    outcome_id,
                    decision_id,
                    action,
                    requested,
                    maximum,
                    as_of,
                    lineage_hash,
                    "released_deferral_without_fill_audit",
                )

        sizing_disposition = str(
            sizing.get("execution_disposition") or ""
        ).strip().lower()
        blocked_reasons = tuple(
            str(item)
            for item in sizing.get("blocked_reasons", ())
            if str(item).strip()
        )
        if (
            sizing_disposition == "blocked"
            or str(sizing.get("status") or "").lower() == "blocked"
        ):
            reasons = blocked_reasons or ("execution_blocked",)
            result = ExecutionOutcome(
                execution_outcome_id=outcome_id,
                experiment_id=experiment.experiment_id,
                experiment_version=experiment.experiment_version,
                decision_id=decision_id,
                requested_action=action,
                outcome_status=OutcomeStatus.RESOLVED,
                execution_disposition=ExecutionDisposition.BLOCKED,
                execution_reason_codes=reasons,
                requested_quantity=requested,
                max_executable_quantity=maximum,
                executed_quantity=Decimal("0"),
                resolved_at=as_of,
                source_lineage_hash=lineage_hash,
            )
            return self._save_terminal("execution", result)
        if sizing_disposition == "deferred_t1":
            return self._execution_insufficient(
                experiment,
                outcome_id,
                decision_id,
                action,
                requested,
                maximum,
                as_of,
                lineage_hash,
                "execution_deferral_audit_missing",
            )

        return ExecutionOutcome(
            execution_outcome_id=outcome_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            decision_id=decision_id,
            requested_action=action,
            outcome_status=OutcomeStatus.PENDING,
            execution_disposition=ExecutionDisposition.PENDING,
            requested_quantity=requested,
            max_executable_quantity=maximum,
            executed_quantity=Decimal("0"),
        )

    def _future_market_sessions(self, market: str, anchor: str, count: int) -> list[str]:
        start = date.fromisoformat(anchor) + timedelta(days=1)
        end = start + timedelta(days=max(370, count * 20))
        return self.calendar.session_dates(
            market,
            start.isoformat(),
            end.isoformat(),
        )[:count]

    @staticmethod
    def _reference_price(
        report: Mapping[str, object],
        context: Mapping[str, object],
    ) -> Decimal | None:
        quote = context.get("quote") if isinstance(context.get("quote"), Mapping) else {}
        price = _decimal(quote.get("price"))
        if price is None or price <= 0:
            price = _decimal(report.get("market_price"))
        return price if price is not None and price > 0 else None

    @staticmethod
    def _market_regime(context: Mapping[str, object]) -> str | None:
        regime = (
            context.get("market_regime")
            if isinstance(context.get("market_regime"), Mapping)
            else {}
        )
        value = str(regime.get("regime") or "").strip()
        return value or None

    @staticmethod
    def _bar_is_eligible(bar: Mapping[str, object]) -> bool:
        if not _finite_ohlc(bar):
            return False
        adjustment = str(bar.get("adjustment") or "").strip().lower()
        return adjustment == "qfq"

    @staticmethod
    def _target_stop_facts(
        bars: list[Mapping[str, object]] | tuple[Mapping[str, object], ...],
        reference: Decimal,
        target_return: Decimal,
        stop_return: Decimal,
    ) -> tuple[bool, bool, bool | None, bool]:
        target_price = reference * (1 + target_return)
        stop_price = reference * (1 + stop_return)
        target_index = stop_index = None
        ambiguous = False
        for index, bar in enumerate(bars):
            high = _decimal(bar.get("high"))
            low = _decimal(bar.get("low"))
            target = high is not None and high >= target_price
            stop = low is not None and low <= stop_price
            if target and target_index is None:
                target_index = index
            if stop and stop_index is None:
                stop_index = index
            if target and stop and target_index == stop_index == index:
                ambiguous = True
        if target_index is None or stop_index is None or target_index == stop_index:
            before = None
        else:
            before = target_index < stop_index
        return target_index is not None, stop_index is not None, before, ambiguous

    @staticmethod
    def _max_drawdown(prices: list[Decimal]) -> Decimal:
        peak = prices[0]
        maximum_drawdown = Decimal("0")
        for price in prices:
            if price > peak:
                peak = price
            if peak > 0:
                maximum_drawdown = min(maximum_drawdown, price / peak - 1)
        return maximum_drawdown

    def _pending_decision(
        self,
        experiment,
        outcome_id: str,
        report: Mapping[str, object],
        symbol: str,
        market: str,
        action: FormalDecisionAction,
        decision_time: datetime,
        reference_price: Decimal,
        horizon: int,
        observation_end: datetime,
        market_regime: str | None,
        reasons: tuple[str, ...],
    ) -> DecisionOutcome:
        return DecisionOutcome(
            outcome_id=outcome_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            decision_id=str(report["decision_id"]),
            symbol=symbol,
            market=market,
            action=action,
            decision_time=decision_time,
            reference_price=reference_price,
            horizon_sessions=horizon,
            observation_end=observation_end,
            outcome_status=OutcomeStatus.PENDING,
            market_regime=market_regime,
            outcome_reason_codes=reasons,
            outcome_policy_version=self.policy.version,
        )

    def _terminal_decision_nonresolved(
        self,
        experiment,
        outcome_id: str,
        report: Mapping[str, object],
        symbol: str,
        market: str,
        action: FormalDecisionAction,
        decision_time: datetime,
        reference_price: Decimal | None,
        horizon: int,
        observation_end: datetime,
        market_regime: str | None,
        as_of: datetime,
        status: OutcomeStatus,
        reasons: tuple[str, ...],
        lineage: object,
    ) -> DecisionOutcome:
        outcome = DecisionOutcome(
            outcome_id=outcome_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            decision_id=str(report["decision_id"]),
            symbol=symbol,
            market=market,
            action=action,
            decision_time=decision_time,
            reference_price=reference_price,
            horizon_sessions=horizon,
            observation_end=observation_end,
            outcome_status=status,
            market_regime=market_regime,
            outcome_reason_codes=reasons,
            source_lineage_hash=_canonical_hash(lineage),
            outcome_policy_version=self.policy.version,
            resolved_at=as_of,
        )
        return self._save_terminal("decision", outcome)

    def _execution_insufficient(
        self,
        experiment,
        outcome_id: str,
        decision_id: str,
        action: FormalDecisionAction,
        requested: Decimal | None,
        maximum: Decimal | None,
        as_of: datetime,
        source_hash: str,
        reason: str,
    ) -> ExecutionOutcome:
        result = ExecutionOutcome(
            execution_outcome_id=outcome_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            decision_id=decision_id,
            requested_action=action,
            outcome_status=OutcomeStatus.INSUFFICIENT_DATA,
            execution_disposition=ExecutionDisposition.BLOCKED,
            execution_reason_codes=(reason,),
            requested_quantity=requested,
            max_executable_quantity=maximum,
            executed_quantity=Decimal("0"),
            resolved_at=as_of,
            source_lineage_hash=source_hash,
        )
        return self._save_terminal("execution", result)

    def _terminal_episode_insufficient(
        self,
        experiment,
        outcome_id: str,
        position_episode_id: str,
        symbol: str,
        opened_at: datetime,
        closed_at: datetime,
        as_of: datetime,
        lineage: object,
        reason: str,
    ) -> TradeEpisodeOutcome:
        result = TradeEpisodeOutcome(
            episode_outcome_id=outcome_id,
            experiment_id=experiment.experiment_id,
            experiment_version=experiment.experiment_version,
            position_episode_id=position_episode_id,
            symbol=symbol,
            outcome_status=OutcomeStatus.INSUFFICIENT_DATA,
            opened_at=opened_at,
            closed_at=closed_at,
            outcome_policy_version=self.policy.version,
            outcome_reason_codes=(reason,),
            source_lineage_hash=_canonical_hash(lineage),
            resolved_at=as_of,
        )
        return self._save_terminal("episode", result)

    def _require_universe_member(self, experiment, symbol: str, market: str):
        snapshot = getattr(experiment, "universe_snapshot", None)
        if snapshot is None:
            if self.experiments is None:
                raise ValueError("experiment universe repository is required for outcome resolution")
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
        if not snapshot.contains(symbol, market):
            raise ValueError("evaluation source is outside frozen experiment universe")
        return snapshot

    def _require_policy(self, experiment) -> None:
        if str(experiment.outcome_policy_version) != self.policy.version:
            raise ValueError("experiment outcome_policy_version does not match resolver policy")

    @staticmethod
    def _normalize_as_of(as_of: datetime | None) -> datetime:
        result = as_of or beijing_now()
        if result.tzinfo is None:
            raise ValueError("evaluation as_of must include timezone information")
        return result

    def _get_existing(self, kind: str, outcome_id: str):
        if self.outcomes is None:
            return None
        getter = getattr(self.outcomes, f"get_{kind}")
        return getter(outcome_id)

    def _save_terminal(self, kind: str, outcome):
        if self.outcomes is None or outcome.outcome_status == OutcomeStatus.PENDING:
            return outcome
        saver = getattr(self.outcomes, f"save_{kind}")
        return saver(outcome)


__all__ = ["DecisionResolution", "OutcomeResolver"]

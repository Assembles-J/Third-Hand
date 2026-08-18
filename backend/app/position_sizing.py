"""Risk-budgeted, deterministic position sizing for shadow reports."""
from __future__ import annotations

from math import floor

from app import decision_config as config
from app.decision_models import DecisionContext, PositionSizingResult
from app.market_adapter import adapter_for_market
from app.position_cap_policy import effective_position_cap_percent


class PositionSizingEngine:
    version = config.SIZING_VERSION

    def size(self, context: DecisionContext, action: str) -> PositionSizingResult:
        # Sizing is deterministic and runs after policy selection.  It can
        # refuse a candidate when required constraints are missing; it never
        # turns a blocked/observation action into an executable one.
        position = context.position
        current_quantity = position.quantity if position else 0.0
        sellable_quantity = (
            position.sellable_quantity
            if position is not None and position.sellable_quantity is not None
            else current_quantity
        )
        common = dict(
            current_quantity=current_quantity,
            current_position_percent=position.position_percent if position else 0.0,
            max_executable_quantity=sellable_quantity,
            sizing_version=self.version,
        )
        quote, instrument, assets = context.quote, context.instrument, context.account.total_assets
        if action in {"BLOCKED", "WATCH", "HOLD"}:
            return PositionSizingResult(status="not_applicable", execution_disposition="not_applicable", **common)
        if action == "EXIT":
            if current_quantity > 0 and sellable_quantity <= 0:
                return PositionSizingResult(
                    status="blocked", suggested_quantity=0.0, target_quantity=current_quantity,
                    target_position_percent=position.position_percent if position else 0.0,
                    execution_disposition="deferred_t1", blocked_reasons=("paper_t1_unsellable_quantity",), **common,
                )
            return PositionSizingResult(
                status="ready", execution_disposition="ready",
                suggested_quantity=sellable_quantity,
                target_quantity=current_quantity - sellable_quantity,
                target_position_percent=(
                    0.0
                    if sellable_quantity >= current_quantity
                    else ((current_quantity - sellable_quantity) * (position.current_price or 0) / assets * 100 if assets else None)
                ),
                **common,
            )
        missing = []
        if not quote:
            missing.append("quote")
        if not instrument or not instrument.lot_size:
            missing.append("instrument.lot_size")
        if assets is None:
            missing.append("account.total_assets")
        if missing:
            return PositionSizingResult(status="blocked", execution_disposition="blocked", blocked_reasons=tuple(missing), **common)
        execution_blockers = self._execution_precheck(context, action)
        if execution_blockers:
            return PositionSizingResult(status="blocked", execution_disposition="blocked", blocked_reasons=execution_blockers, **common)
        lot, entry = instrument.lot_size, quote.price
        effective_cap_percent = effective_position_cap_percent(context)
        maximum_target = floor(assets * (effective_cap_percent / 100.0) / entry)
        maximum_target_lotted = self._round_down(maximum_target, lot)
        if action == "REDUCE":
            # Evidence and sizing consume the same effective concentration cap.
            # A personal rule may tighten the system hard cap, so REDUCE cannot
            # aim at a looser target than the rule that produced position.above_max.
            target_quantity = maximum_target_lotted
            desired_reduction = max(0.0, current_quantity - target_quantity)
            if desired_reduction > 0 and sellable_quantity <= 0:
                return PositionSizingResult(
                    status="blocked", suggested_quantity=0.0, target_quantity=current_quantity,
                    target_position_percent=position.position_percent if position else 0.0,
                    quantity_by_position_cap=target_quantity, lot_size=lot, entry_price=entry,
                    execution_disposition="deferred_t1", blocked_reasons=("paper_t1_unsellable_quantity",), **common,
                )
            suggested = min(desired_reduction, sellable_quantity)
            resulting_quantity = current_quantity - suggested
            return PositionSizingResult(
                status="ready", execution_disposition="ready",
                suggested_quantity=suggested,
                target_quantity=resulting_quantity,
                target_position_percent=round(resulting_quantity * entry / assets * 100, 4),
                quantity_by_position_cap=target_quantity,
                lot_size=lot,
                entry_price=entry,
                **common,
            )
        if action not in {"OPEN", "ADD"}:
            return PositionSizingResult(status="not_applicable", execution_disposition="not_applicable", **common)
        if quote.volume is None or quote.volume <= 0:
            return PositionSizingResult(status="blocked", execution_disposition="blocked", blocked_reasons=("quote.volume",), lot_size=lot, entry_price=entry, **common)
        # The final quantity is capped by four independent constraints: loss
        # budget, available cash, the shared effective concentration cap, and
        # market liquidity.
        invalidation_price = entry * 0.95
        risk_per_share = entry - invalidation_price
        risk_capital = assets * 0.01
        quantity_by_risk = floor(risk_capital / risk_per_share)
        quantity_by_cash = floor(context.account.available_cash / entry)
        quantity_by_position_cap = max(0.0, maximum_target_lotted - current_quantity)
        quantity_by_liquidity = floor(quote.volume * config.MAX_LIQUIDITY_VOLUME_FRACTION)
        candidate = self._round_down(
            min(quantity_by_risk, quantity_by_cash, quantity_by_position_cap, quantity_by_liquidity),
            lot,
        )
        if candidate < lot:
            return PositionSizingResult(
                status="blocked", execution_disposition="blocked",
                quantity_by_risk=quantity_by_risk,
                quantity_by_cash=quantity_by_cash,
                quantity_by_position_cap=quantity_by_position_cap,
                quantity_by_liquidity=quantity_by_liquidity,
                lot_size=lot,
                entry_price=entry,
                invalidation_price=invalidation_price,
                risk_per_share=risk_per_share,
                risk_capital=risk_capital,
                blocked_reasons=("quantity_below_one_lot",),
                **common,
            )
        target = current_quantity + candidate
        return PositionSizingResult(
            status="ready", execution_disposition="ready",
            suggested_quantity=candidate,
            target_quantity=target,
            target_position_percent=round(target * entry / assets * 100, 4),
            quantity_by_risk=quantity_by_risk,
            quantity_by_cash=quantity_by_cash,
            quantity_by_position_cap=quantity_by_position_cap,
            quantity_by_liquidity=quantity_by_liquidity,
            lot_size=lot,
            entry_price=entry,
            invalidation_price=invalidation_price,
            risk_per_share=risk_per_share,
            risk_capital=risk_capital,
            **common,
        )

    @staticmethod
    def _round_down(quantity: float, lot_size: int) -> float:
        return float(floor(max(0, quantity) / lot_size) * lot_size)

    @staticmethod
    def _execution_precheck(context: DecisionContext, action: str) -> tuple[str, ...]:
        """Check market execution prerequisites before deriving a trade size.

        This is intentionally stricter than research eligibility: an instrument
        can be researched without being executable in the single-CNY paper
        ledger. The guard prevents a numeric sizing result from suggesting a
        trade that the execution boundary must reject anyway.
        """
        if action not in {"OPEN", "ADD", "REDUCE", "EXIT"}:
            return ()
        instrument = context.instrument
        if instrument is None:
            return ("execution_instrument_metadata_required",)
        adapter = adapter_for_market(instrument.market)
        if adapter is None:
            return ("execution_market_rule_unavailable",)
        if instrument.currency != adapter.trading_currency:
            return ("execution_instrument_currency_conflict",)
        if instrument.currency != context.account.account_currency:
            # A Stock Connect receipt may record HKD price and CNY settlement,
            # but that is an audit fact, not a generic FX/multi-currency paper
            # ledger. Do not silently turn it into an executable conversion.
            return ("execution_foreign_currency_quote_unsupported",)
        if adapter.paper_fee_schedule == "UNCONFIGURED":
            return ("execution_fee_schedule_unconfigured",)
        return ()

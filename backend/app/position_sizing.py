"""Risk-budgeted, deterministic position sizing for shadow reports."""
from __future__ import annotations

from math import floor

from app import decision_config as config
from app.decision_models import DecisionContext, PositionSizingResult
from app.market_adapter import adapter_for_market


class PositionSizingEngine:
    version = config.SIZING_VERSION

    def size(self, context: DecisionContext, action: str) -> PositionSizingResult:
        # Sizing is deterministic and runs after policy selection.  It can
        # refuse a candidate when required constraints are missing; it never
        # turns a blocked/observation action into an executable one.
        position = context.position
        current_quantity = position.quantity if position else 0.0
        common = dict(current_quantity=current_quantity, current_position_percent=position.position_percent if position else 0.0, sizing_version=self.version)
        if action in {"BLOCKED", "WATCH", "HOLD"}:
            return PositionSizingResult(status="not_applicable", **common)
        if action == "EXIT":
            return PositionSizingResult(status="ready", suggested_quantity=current_quantity, target_quantity=0.0, target_position_percent=0.0, **common)
        quote, instrument, assets = context.quote, context.instrument, context.account.total_assets
        missing = []
        if not quote: missing.append("quote")
        if not instrument or not instrument.lot_size: missing.append("instrument.lot_size")
        if assets is None: missing.append("account.total_assets")
        if missing:
            return PositionSizingResult(status="blocked", blocked_reasons=tuple(missing), **common)
        execution_blockers = self._execution_precheck(context, action)
        if execution_blockers:
            return PositionSizingResult(status="blocked", blocked_reasons=execution_blockers, **common)
        lot, entry = instrument.lot_size, quote.price
        if action == "REDUCE":
            # The workbench has one transparent, system-wide sizing policy instead
            # of per-stock text plans: no single name above 20% of portfolio value.
            target_quantity = self._round_down(assets * 0.20 / entry, lot)
            suggested = max(0.0, current_quantity - target_quantity)
            return PositionSizingResult(status="ready", suggested_quantity=suggested, target_quantity=current_quantity - suggested, target_position_percent=round((current_quantity - suggested) * entry / assets * 100, 4), quantity_by_position_cap=target_quantity, lot_size=lot, entry_price=entry, **common)
        if action not in {"OPEN", "ADD"}:
            return PositionSizingResult(status="not_applicable", **common)
        if quote.volume is None or quote.volume <= 0:
            return PositionSizingResult(status="blocked", blocked_reasons=("quote.volume",), lot_size=lot, entry_price=entry, **common)
        # The final quantity is capped by four independent constraints: loss
        # budget, available cash, portfolio concentration, and market liquidity.
        invalidation_price = entry * 0.95
        risk_per_share = entry - invalidation_price
        risk_capital = assets * 0.01
        quantity_by_risk = floor(risk_capital / risk_per_share)
        quantity_by_cash = floor(context.account.available_cash / entry)
        maximum_target = floor(assets * 0.20 / entry)
        quantity_by_position_cap = max(0.0, maximum_target - current_quantity)
        quantity_by_liquidity = floor(quote.volume * config.MAX_LIQUIDITY_VOLUME_FRACTION)
        candidate = self._round_down(min(quantity_by_risk, quantity_by_cash, quantity_by_position_cap, quantity_by_liquidity), lot)
        if candidate < lot:
            return PositionSizingResult(status="blocked", quantity_by_risk=quantity_by_risk, quantity_by_cash=quantity_by_cash, quantity_by_position_cap=quantity_by_position_cap, quantity_by_liquidity=quantity_by_liquidity, lot_size=lot, entry_price=entry, invalidation_price=invalidation_price, risk_per_share=risk_per_share, risk_capital=risk_capital, blocked_reasons=("quantity_below_one_lot",), **common)
        target = current_quantity + candidate
        return PositionSizingResult(status="ready", suggested_quantity=candidate, target_quantity=target, target_position_percent=round(target * entry / assets * 100, 4), quantity_by_risk=quantity_by_risk, quantity_by_cash=quantity_by_cash, quantity_by_position_cap=quantity_by_position_cap, quantity_by_liquidity=quantity_by_liquidity, lot_size=lot, entry_price=entry, invalidation_price=invalidation_price, risk_per_share=risk_per_share, risk_capital=risk_capital, **common)

    @staticmethod
    def _round_down(quantity: float, lot_size: int) -> float:
        return float(floor(max(0, quantity) / lot_size) * lot_size)

    @staticmethod
    def _execution_precheck(context: DecisionContext, action: str) -> tuple[str, ...]:
        """Check market execution prerequisites before deriving a trade size.

        This is intentionally stricter than research eligibility: an instrument
        can be researched without a paper ledger capable of settling its
        currency.  The guard prevents a numeric sizing result from suggesting a
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
        if context.account.account_currency != instrument.currency:
            return ("execution_account_currency_mismatch",)
        if adapter.paper_fee_schedule == "UNCONFIGURED":
            return ("execution_fee_schedule_unconfigured",)
        return ()

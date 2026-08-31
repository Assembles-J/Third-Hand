"""Deterministic user-driven paper-order preflight and execution.

A manual paper order is a USER action, not a Formal Decision or an AI action.
The service therefore never manufactures a decision id and never accepts a
client-supplied fill price. It validates the latest locally persisted quote,
exchange session, market/lot rules, cash and lot sellability, then delegates the
actual ledger mutation to ``PortfolioStore.execute_paper_trade``.

The normal paper account is currently CNY-only. HK/US capability is exposed
explicitly but remains fail-closed until a separately accepted fee/currency
settlement contract exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Callable

from app import decision_config as config
from app.execution_precheck import execution_quote_observed_at
from app.market_adapter import adapter_for_market, adapter_for_symbol
from app.time_utils import beijing_now
from app.trading_calendar import TradingCalendarService


BEIJING_TZ = timezone(timedelta(hours=8))
_CLIENT_ORDER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ManualPaperOrderRejected(ValueError):
    """Typed fail-closed rejection carrying the latest server preflight."""

    def __init__(self, reason_code: str, capability: dict[str, object]) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.capability = capability


@dataclass(frozen=True)
class ManualPaperOrderService:
    store: object
    calendar: TradingCalendarService
    max_quote_age_seconds: int
    now_provider: Callable[[], datetime]

    def __init__(
        self,
        store,
        *,
        calendar: TradingCalendarService | None = None,
        max_quote_age_seconds: int = config.EXECUTION_QUOTE_MAX_AGE_SECONDS,
        now_provider: Callable[[], datetime] = beijing_now,
    ) -> None:
        object.__setattr__(self, "store", store)
        object.__setattr__(self, "calendar", calendar or TradingCalendarService())
        object.__setattr__(self, "max_quote_age_seconds", max(1, int(max_quote_age_seconds)))
        object.__setattr__(self, "now_provider", now_provider)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol or "").strip().upper()

    @staticmethod
    def _normalize_side(side: str) -> str:
        return str(side or "").strip().upper()

    @staticmethod
    def _parse_time(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=BEIJING_TZ)
        return parsed.astimezone(BEIJING_TZ)

    def _identity(self, symbol: str):
        metadata = self.store.instrument_metadata(symbol)
        market = str((metadata or {}).get("market") or "").strip().upper()
        adapter = adapter_for_market(market) if market else adapter_for_symbol(symbol)
        return metadata, adapter

    def _latest_quote(self, symbol: str) -> dict[str, object] | None:
        return next(iter(self.store.cached_quotes([symbol])), None)

    @staticmethod
    def _position(account: dict[str, object], symbol: str) -> dict[str, object] | None:
        return next(
            (
                dict(item)
                for item in account.get("positions", [])
                if str(item.get("symbol") or "").strip().upper() == symbol
            ),
            None,
        )

    @staticmethod
    def _max_buy_quantity(cash: float, price: float, lot_size: int) -> float:
        if cash <= 0 or price <= 0 or lot_size <= 0:
            return 0.0
        candidate = math.floor(cash / price / lot_size) * lot_size
        while candidate > 0:
            gross = float(candidate) * price
            fee = max(5.0, gross * 0.0003)
            if gross + fee <= cash + 1e-9:
                return float(candidate)
            candidate -= lot_size
        return 0.0

    def capability(self, symbol: str) -> dict[str, object]:
        """Return the authoritative current manual-order capability projection."""

        symbol = self._normalize_symbol(symbol)
        now = self.now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=BEIJING_TZ)
        else:
            now = now.astimezone(BEIJING_TZ)

        metadata, adapter = self._identity(symbol)
        account = self.store.paper_account()
        position = self._position(account, symbol)
        quote = self._latest_quote(symbol)
        quote_price = float((quote or {}).get("price") or 0)
        observed_text = execution_quote_observed_at(quote)
        observed_at = self._parse_time(observed_text)

        market = adapter.market if adapter is not None else None
        currency = adapter.trading_currency if adapter is not None else None
        lot_size = int((metadata or {}).get("lot_size") or (adapter.default_lot_size if adapter else 0) or 0)
        sellable = float((position or {}).get("sellable_quantity") or 0)
        locked = float((position or {}).get("locked_quantity") or 0)
        held = float((position or {}).get("quantity") or 0)
        cash = float(account.get("available_cash") or 0)

        reasons: list[str] = []
        if adapter is None:
            reasons.append("paper_manual_order_market_unavailable")
        elif adapter.market == "HK":
            reasons.append("paper_hk_execution_not_configured")
        elif adapter.market != "CN":
            reasons.append("paper_foreign_market_execution_not_supported")
        elif adapter.paper_fee_schedule != "CN_A_STANDARD":
            reasons.append("paper_fee_schedule_unconfigured")

        if lot_size <= 0:
            reasons.append("paper_instrument_lot_size_required")

        market_open = bool(adapter and self.calendar.is_market_open(adapter.market, moment=now))
        if adapter is not None and adapter.market == "CN" and not market_open:
            reasons.append("paper_manual_order_market_closed")

        if not quote or quote_price <= 0:
            reasons.append("paper_manual_order_quote_missing")
        elif observed_at is None:
            reasons.append("paper_manual_order_quote_time_unknown")
        elif adapter is not None and not self.calendar.is_market_open(adapter.market, moment=observed_at):
            reasons.append("paper_manual_order_quote_outside_session")
        elif (now - observed_at).total_seconds() > self.max_quote_age_seconds:
            reasons.append("paper_manual_order_quote_stale")

        market_executable = not any(
            reason
            in {
                "paper_manual_order_market_unavailable",
                "paper_hk_execution_not_configured",
                "paper_foreign_market_execution_not_supported",
                "paper_fee_schedule_unconfigured",
                "paper_instrument_lot_size_required",
                "paper_manual_order_market_closed",
                "paper_manual_order_quote_missing",
                "paper_manual_order_quote_time_unknown",
                "paper_manual_order_quote_outside_session",
                "paper_manual_order_quote_stale",
            }
            for reason in reasons
        )

        max_buy = self._max_buy_quantity(cash, quote_price, lot_size) if market_executable else 0.0
        max_sell = sellable if market_executable else 0.0
        return {
            "symbol": symbol,
            "market": market,
            "currency": currency,
            "paper_account_currency": "CNY",
            "executable": market_executable,
            "reason_codes": reasons,
            "lot_size": lot_size or None,
            "price_tick": (metadata or {}).get("price_tick"),
            "market_open": market_open,
            "quote_price": quote_price if quote_price > 0 else None,
            "quote_observed_at": observed_text,
            "quote_source": str((quote or {}).get("source") or "") or None,
            "available_cash": cash,
            "held_quantity": held,
            "sellable_quantity": sellable,
            "locked_quantity": locked,
            "next_eligible_sell_at": (position or {}).get("next_eligible_sell_at"),
            "max_buy_quantity": max_buy,
            "max_sell_quantity": max_sell,
        }

    @staticmethod
    def _validate_client_order_id(client_order_id: str) -> str:
        value = str(client_order_id or "").strip()
        if not _CLIENT_ORDER_ID.fullmatch(value):
            raise ValueError("paper_manual_order_client_id_invalid")
        return value

    def _existing_fill(self, trade_id: str) -> dict[str, object] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_trading_logs WHERE id=? LIMIT 1",
                (trade_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _same_order(existing: dict[str, object], *, symbol: str, side: str, quantity: float) -> bool:
        return (
            str(existing.get("symbol") or "").strip().upper() == symbol
            and str(existing.get("side") or "").strip().upper() == side
            and abs(float(existing.get("quantity") or 0) - quantity) <= 1e-9
            and str(existing.get("reason") or "").startswith("user_manual_paper_order:")
        )

    def submit(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict[str, object]:
        """Validate and synchronously fill one user paper order at server quote."""

        client_order_id = self._validate_client_order_id(client_order_id)
        symbol = self._normalize_symbol(symbol)
        side = self._normalize_side(side)
        if side not in {"BUY", "SELL"}:
            raise ValueError("paper_manual_order_side_invalid")
        try:
            quantity = float(quantity)
        except (TypeError, ValueError) as error:
            raise ValueError("paper_manual_order_quantity_invalid") from error
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("paper_manual_order_quantity_invalid")

        trade_id = f"manual:{client_order_id}"
        existing = self._existing_fill(trade_id)
        if existing is not None:
            if self._same_order(existing, symbol=symbol, side=side, quantity=quantity):
                return {"status": "executed", "idempotent_replay": True, "fill": existing}
            raise ValueError("paper_manual_order_id_conflict")

        capability = self.capability(symbol)
        if not capability["executable"]:
            reason = str((capability.get("reason_codes") or ["paper_manual_order_unavailable"])[0])
            raise ManualPaperOrderRejected(reason, capability)

        lot_size = int(capability.get("lot_size") or 0)
        if lot_size <= 0:
            raise ManualPaperOrderRejected("paper_instrument_lot_size_required", capability)
        if quantity % lot_size != 0:
            raise ManualPaperOrderRejected("paper_manual_order_quantity_violates_lot", capability)

        if side == "BUY" and quantity > float(capability.get("max_buy_quantity") or 0) + 1e-9:
            raise ManualPaperOrderRejected("paper_manual_order_insufficient_cash", capability)
        if side == "SELL":
            held = float(capability.get("held_quantity") or 0)
            sellable = float(capability.get("sellable_quantity") or 0)
            if held <= 0:
                raise ManualPaperOrderRejected("paper_manual_order_no_position", capability)
            if sellable <= 0:
                raise ManualPaperOrderRejected("paper_manual_order_t1_locked", capability)
            if quantity > sellable + 1e-9:
                raise ManualPaperOrderRejected("paper_manual_order_exceeds_sellable", capability)

        price = float(capability.get("quote_price") or 0)
        quote_source = str(capability.get("quote_source") or "") or None
        observed_at = str(capability.get("quote_observed_at") or "") or None
        name = symbol
        quote = self._latest_quote(symbol)
        if quote:
            name = str(quote.get("name") or symbol)

        try:
            fill = self.store.execute_paper_trade(
                trade_id=trade_id,
                symbol=symbol,
                name=name,
                side=side,
                quantity=quantity,
                price=price,
                decision_id=None,
                reason=f"user_manual_paper_order:{client_order_id}",
                execution_quote_at=observed_at,
                execution_quote_source=quote_source,
                fill_price_mode="USER_MANUAL_LATEST_ELIGIBLE_OBSERVED_QUOTE",
            )
        except Exception:
            # The ledger mutation and final log insert share one SQLite
            # transaction. A concurrent duplicate therefore rolls back before
            # this lookup and is safe only if its immutable request matches.
            existing = self._existing_fill(trade_id)
            if existing is not None and self._same_order(
                existing,
                symbol=symbol,
                side=side,
                quantity=quantity,
            ):
                return {"status": "executed", "idempotent_replay": True, "fill": existing}
            raise

        return {"status": "executed", "idempotent_replay": False, "fill": fill}


__all__ = ["ManualPaperOrderRejected", "ManualPaperOrderService"]

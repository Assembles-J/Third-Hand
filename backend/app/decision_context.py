"""Read-only construction of a versioned, immutable decision context."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from app.data_quality import summarize_data_quality
from app.decision_models import (
    AccountSnapshot, DailyBarSummary, DecisionContext, EventSnapshot,
    InstrumentSnapshot, MarketFlowSnapshot, MarketRegimeSnapshot, PersonalRuleSnapshot,
    PositionSnapshot, QuoteSnapshot, RelativeStrengthSnapshot, RiskSnapshot,
    TechnicalSnapshot, TradePlanSnapshot,
)
from app.time_utils import beijing_now


CONTEXT_SCHEMA_VERSION = "context-v1"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class DecisionContextBuilder:
    """Build contexts from persisted data only; it never calls an LLM or emits an action."""

    def __init__(self, store, technical_service=None) -> None:
        self.store = store
        self.technical_service = technical_service

    @staticmethod
    def _symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized

    @staticmethod
    def _selected_rule(rules: list[dict[str, object]], symbol: str) -> dict[str, object] | None:
        enabled = [rule for rule in rules if rule.get("enabled")]
        return next(
            (rule for rule in enabled if rule.get("scope") == "symbol" and rule.get("symbol") == symbol),
            next((rule for rule in enabled if rule.get("scope") == "global"), None),
        )

    def build(
        self,
        symbol: str,
        *,
        holdings_override: list[dict[str, object]] | None = None,
        available_cash_override: float | None = None,
    ) -> DecisionContext:
        # The context is a reproducible snapshot assembled from persisted
        # caches.  Keep upstream fetching and LLM calls out of this boundary so
        # a saved decision can be audited against stable input data.
        symbol = self._symbol(symbol)
        # Paper trading must reason from its own ledger, never from the user's
        # real holdings.  The override keeps the same canonical context schema
        # while making the simulated account an auditable decision input.
        holdings = holdings_override if holdings_override is not None else self.store.list()
        holding = next((item for item in holdings if str(item["symbol"]).strip().upper() == symbol), None)
        research_target = next(
            (item for item in self.store.research_targets() if str(item["symbol"]).strip().upper() == symbol),
            None,
        )
        quotes = {str(item["symbol"]).strip().upper(): item for item in self.store.cached_quotes(
            [str(item["symbol"]) for item in holdings] + [symbol]
        )}
        quote = quotes.get(symbol)
        bars = self.store.daily_prices(symbol)
        risk = self.store.cached_risk(symbol)
        plan = self.store.trade_plan(symbol)
        rule = self._selected_rule(self.store.personal_rules(), symbol)
        instrument = self.store.instrument_metadata(symbol)
        portfolio_item = self._portfolio_item(symbol)
        events = self._events(symbol)

        all_market_values: list[float] = []
        for account_holding in holdings:
            account_quote = quotes.get(str(account_holding["symbol"]).strip().upper())
            if not account_quote or account_quote.get("price") is None:
                all_market_values = []
                break
            all_market_values.append(float(account_holding["quantity"]) * float(account_quote["price"]))
        total_market_value = sum(all_market_values) if len(all_market_values) == len(holdings) else None
        cash = float(available_cash_override) if available_cash_override is not None else float(self.store.available_cash()["available_cash"])
        total_assets = cash + total_market_value if total_market_value is not None else None
        price = float(quote["price"]) if quote and quote.get("price") is not None else None
        position = self._position(holding, price, total_assets)
        technical = self._technical(symbol, bars)
        market_regime = self._market_regime(portfolio_item)
        market_flow = self._market_flow()
        relative_strength = self._relative_strength(portfolio_item)
        quality = summarize_data_quality(
            has_quote=price is not None, daily_bar_count=len(bars), total_assets_available=total_assets is not None,
            plan_enabled=bool(plan and plan.get("enabled")), has_risk=risk is not None,
            has_market_regime=market_regime is not None, has_relative_strength=relative_strength is not None,
            has_events=bool(events), has_instrument=instrument is not None, has_position=position is not None,
            has_personal_rule=rule is not None, quote_as_of=str((quote or {}).get("as_of") or "") or None,
            quote_retrieved_at=str((quote or {}).get("retrieved_at") or "") or None,
            daily_bar_as_of=str(bars[-1].get("trading_date") or "") if bars else None,
            risk_as_of=str((risk or {}).get("as_of") or "") or None,
            market_as_of=market_regime.as_of if market_regime else None,
            market_retrieved_at=market_flow.retrieved_at if market_flow else None,
        )
        account = AccountSnapshot(
            available_cash=cash, total_market_value=total_market_value, total_assets=total_assets,
            cash_percent=round(cash / total_assets * 100, 4) if total_assets else None,
        )
        payload = {
            "symbol": symbol, "name": str(holding["name"]) if holding else str(research_target["name"]) if research_target else symbol,
            "decision_horizon": str(plan.get("horizon", "swing")) if plan else "swing",
            "account": account, "position": position, "quote": self._quote(quote),
            "daily_bars": self._daily_bars(bars), "technical": technical, "risk": self._risk(risk),
            "market_regime": market_regime, "market_flow": market_flow, "relative_strength": relative_strength, "events": events,
            "trade_plan": self._plan(plan, symbol), "personal_rule": self._rule(rule),
            "instrument": self._instrument(instrument), "data_quality": quality,
            "source_versions": self._source_versions(),
        }
        # Reports retain this hash, allowing later comparisons to distinguish a
        # changed conclusion from a changed input snapshot.
        input_hash = _canonical_hash({key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value for key, value in payload.items()})
        return DecisionContext(
            context_id=str(uuid4()), generated_at=beijing_now(), input_hash=input_hash, **payload,
        )

    def _portfolio_item(self, symbol: str) -> dict[str, object] | None:
        payload = self.store.cached_portfolio_analysis() or {}
        return next((item for item in payload.get("items", []) if str(item.get("symbol", "")).upper() == symbol), None)

    def _events(self, symbol: str) -> tuple[EventSnapshot, ...]:
        # Cached AI analysis is research-only.  Its directional label must not
        # enter deterministic evidence because ActionPolicy consumes negative
        # event evidence for ADD/REDUCE decisions.  A future policy event must
        # be a separately verified, deterministic feature.
        results = []
        for item in self.store.cached_content([symbol], limit=10):
            ai = item.get("ai_analysis") or {}
            results.append(EventSnapshot(
                event_id=str(item.get("id", "")), title=str(item.get("title", "")), impact="uncertain",
                source=str(item.get("source_name", "content_cache")), source_reference=item.get("source_url"),
                published_at=str(item["published_at"]) if item.get("published_at") else None,
                summary=str(ai.get("summary") or item.get("explanation") or "") or None,
            ))
            if len(results) == 5:
                break
        return tuple(results)

    def _technical(self, symbol: str, bars: list[dict[str, object]]) -> TechnicalSnapshot | None:
        if not self.technical_service or len(bars) < 60:
            return None
        try:
            item = self.technical_service.assess(symbol, bars)
            return TechnicalSnapshot(**{key: item.get(key) for key in TechnicalSnapshot.model_fields})
        except Exception:
            return None

    @staticmethod
    def _position(holding, price, total_assets):
        if not holding:
            return None
        quantity, cost = float(holding["quantity"]), float(holding["average_cost"])
        market_value = quantity * price if price is not None else None
        cost_value = quantity * cost
        return PositionSnapshot(
            quantity=quantity, average_cost=cost, opened_at=str(holding.get("created_at") or "") or None, current_price=price, market_value=market_value,
            cost_value=cost_value, unrealized_pnl=market_value - cost_value if market_value is not None else None,
            unrealized_pnl_percent=(market_value / cost_value - 1) * 100 if market_value is not None and cost_value else None,
            position_percent=market_value / total_assets * 100 if market_value is not None and total_assets else None,
        )

    @staticmethod
    def _quote(item):
        if not item or item.get("price") is None:
            return None
        values = {key: item.get(key) for key in QuoteSnapshot.model_fields}
        values["price"] = float(values["price"])
        values["source"] = str(values["source"] or "market_quote_cache")
        values["freshness_status"] = str(item.get("refresh_status") or item.get("freshness_status") or "unknown")
        return QuoteSnapshot(**values)

    @staticmethod
    def _daily_bars(bars):
        return DailyBarSummary(
            count=len(bars), first_trading_date=str(bars[0]["trading_date"]) if bars else None,
            last_trading_date=str(bars[-1]["trading_date"]) if bars else None,
            last_close=float(bars[-1]["close"]) if bars else None,
            source=str(bars[-1].get("source")) if bars else None,
        )

    @staticmethod
    def _risk(item):
        if not item:
            return None
        values = {key: item.get(key) for key in RiskSnapshot.model_fields if key != "source"}
        return RiskSnapshot(**values)

    @staticmethod
    def _market_regime(item):
        value = (item or {}).get("decision_snapshot", {}).get("market_regime")
        if not value:
            return None
        return MarketRegimeSnapshot(status=str(value.get("status", "unknown")), regime=value.get("regime"), source=value.get("source"), as_of=value.get("as_of"))

    def _market_flow(self) -> MarketFlowSnapshot | None:
        payload = self.store.cached_market_intelligence("overview")
        if not payload:
            return None
        main = ((payload.get("fund_flow") or {}).get("主力") or {}).get("net_amount")
        northbound_rows = payload.get("northbound") or []
        northbound = next((item.get("net_amount") for item in northbound_rows if item.get("net_amount") is not None), None)
        breadth = payload.get("breadth") or {}
        return MarketFlowSnapshot(
            retrieved_at=str(payload.get("retrieved_at") or "") or None,
            data_health=str(payload.get("data_health") or "unknown"),
            main_net_amount=float(main) if main is not None else None,
            northbound_net_amount=float(northbound) if northbound is not None else None,
            rise_count=int(breadth["rise_count"]) if breadth.get("rise_count") is not None else None,
            fall_count=int(breadth["fall_count"]) if breadth.get("fall_count") is not None else None,
            source=str(payload.get("source") or "market_intelligence_cache"),
        )

    @staticmethod
    def _relative_strength(item):
        value = (item or {}).get("decision_snapshot", {}).get("relative_strength")
        if not value:
            return None
        return RelativeStrengthSnapshot(status=str(value.get("status", "unknown")), benchmark_symbol=value.get("benchmark_symbol"), benchmark_name=value.get("benchmark_name"), label=value.get("label"))

    @staticmethod
    def _plan(item, symbol: str):
        if not item:
            # A draft keeps analysis moving without silently enabling a trading plan.
            return TradePlanSnapshot(
                plan_id=f"draft:{symbol}", horizon="swing",
                thesis="系统草稿：待用户确认持有依据、行业逻辑与估值假设。",
                entry_condition="草稿未启用：不作为开仓或加仓条件。",
                add_condition="草稿未启用：不作为加仓条件。",
                reduce_condition="风险恶化或仓位超过上限时复核。",
                exit_condition="核心逻辑失效、事实被证伪或触发风险边界时复核。",
                max_position_percent=20.0, risk_budget_percent=1.0,
                enabled=False, version=0, is_draft=True,
            )
        return TradePlanSnapshot(plan_id=str(item["id"]), horizon=str(item["horizon"]), thesis=str(item["thesis"]), entry_condition=str(item["entry_condition"]), add_condition=str(item["add_condition"]), reduce_condition=str(item["reduce_condition"]), exit_condition=str(item["exit_condition"]), max_position_percent=float(item["max_position_percent"]), risk_budget_percent=float(item["risk_budget_percent"]), invalidation_price=item.get("invalidation_price"), enabled=bool(item["enabled"]), version=int(item["version"]), structured_conditions=tuple(item.get("structured_conditions") or ()), is_draft=False)

    @staticmethod
    def _rule(item):
        if not item:
            return None
        return PersonalRuleSnapshot(rule_id=str(item["id"]), scope=str(item["scope"]), max_position_percent=float(item["max_position_percent"]), loss_review_percent=float(item["loss_review_percent"]), volatility_review_percent=float(item["volatility_review_percent"]), enabled=bool(item["enabled"]), version=int(item["version"]))

    @staticmethod
    def _instrument(item):
        if not item:
            return None
        return InstrumentSnapshot(symbol=str(item["symbol"]), market=str(item["market"]), currency=str(item["currency"]), lot_size=item.get("lot_size"), price_tick=item.get("price_tick"), source=str(item["source"]), as_of=str(item["as_of"]))

    @staticmethod
    def _source_versions() -> dict[str, str]:
        return {"context_schema": CONTEXT_SCHEMA_VERSION, "quote": "market_quote_cache-v1", "daily_bars": "daily_price_cache-v1", "risk": "risk_cache-v1", "events": "content_cache-v1", "market_flow": "market_intelligence_cache-v1", "trade_plan": "trade_plans-v1"}

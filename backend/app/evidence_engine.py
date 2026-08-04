"""Deterministically translate a DecisionContext into source-linked evidence."""
from __future__ import annotations

from app import decision_config as config
from app.decision_models import DecisionContext, EvidenceItem


def _item(evidence_id: str, category: str, direction: str, strength: float, title: str, description: str, *, value=None, threshold=None, source: str, as_of=None, fresh: bool = True, rule_id=None, source_reference=None) -> EvidenceItem:
    return EvidenceItem(evidence_id=evidence_id, category=category, direction=direction, strength=strength, title=title, description=description, value=value, threshold=threshold, source=source, as_of=as_of, fresh=fresh, rule_id=rule_id, source_reference=source_reference)


class EvidenceEngine:
    """Evidence only: this class does not select or rank trading actions."""

    version = config.EVIDENCE_VERSION

    def build(self, context: DecisionContext) -> tuple[EvidenceItem, ...]:
        # Evidence is normalized before policy evaluation.  The stable IDs are
        # also the only citations that downstream AI output may reference.
        evidence: list[EvidenceItem] = [self._data_quality(context)]
        evidence.extend(self._position(context))
        evidence.extend(self._technical(context))
        evidence.extend(self._risk(context))
        evidence.extend(self._market(context))
        evidence.extend(self._relative(context))
        evidence.extend(self._events(context))
        evidence.extend(self._plan(context))
        result = tuple(sorted(evidence, key=lambda item: item.evidence_id))
        if len({item.evidence_id for item in result}) != len(result):
            raise ValueError("evidence IDs must be unique")
        return result

    @staticmethod
    def _data_quality(context: DecisionContext) -> EvidenceItem:
        quality = context.data_quality
        direction = "positive" if quality.status == "ready" else "uncertain" if quality.status == "degraded" else "negative"
        return _item("data_quality.summary", "data_quality", direction, quality.score_percent / 100, "数据质量", f"数据质量为 {quality.status}，完整度 {quality.score_percent}%", value=quality.status, threshold=100, source="decision_context", as_of=context.generated_at, fresh=True)

    @staticmethod
    def _position(context: DecisionContext) -> list[EvidenceItem]:
        position, rule = context.position, context.personal_rule
        if not position or not rule or position.position_percent is None:
            return []
        result: list[EvidenceItem] = []
        percent, cap = position.position_percent, rule.max_position_percent
        if percent > cap:
            excess_percent = (percent - cap) / cap * 100 if cap else 100
            strength = .5 if excess_percent <= config.POSITION_CAP_EXCESS_MILD_PERCENT else .7 if excess_percent <= config.POSITION_CAP_EXCESS_MEDIUM_PERCENT else .9
            result.append(_item("position.above_max", "position", "negative", strength, "仓位超过上限", f"当前仓位 {percent:.2f}% 高于规则上限 {cap:.2f}%", value=percent, threshold=cap, source="decision_context", as_of=context.generated_at, rule_id=rule.rule_id))
        elif percent >= cap * config.NEAR_POSITION_CAP_RATIO:
            result.append(_item("position.near_max", "position", "uncertain", .4, "仓位接近上限", f"当前仓位 {percent:.2f}% 接近规则上限 {cap:.2f}%", value=percent, threshold=cap, source="decision_context", as_of=context.generated_at, rule_id=rule.rule_id))
        if position.unrealized_pnl_percent is not None and position.unrealized_pnl_percent <= -rule.loss_review_percent:
            result.append(_item("position.loss_exceeds_review_threshold", "position", "negative", .7, "亏损达到复核阈值", f"浮动收益 {position.unrealized_pnl_percent:.2f}% 低于复核阈值 -{rule.loss_review_percent:.2f}%", value=position.unrealized_pnl_percent, threshold=-rule.loss_review_percent, source="decision_context", as_of=context.generated_at, rule_id=rule.rule_id))
        if position.unrealized_pnl_percent is not None and position.unrealized_pnl_percent >= config.LARGE_PROFIT_PERCENT:
            result.append(_item("position.profit_large", "position", "positive", .5, "浮盈较大", f"浮动收益 {position.unrealized_pnl_percent:.2f}%", value=position.unrealized_pnl_percent, threshold=config.LARGE_PROFIT_PERCENT, source="decision_context", as_of=context.generated_at))
        if context.account.cash_percent is not None and context.account.cash_percent <= config.CASH_CONSTRAINED_PERCENT:
            result.append(_item("position.cash_constrained", "position", "negative", .6, "可用现金受限", f"现金占总资产 {context.account.cash_percent:.2f}%", value=context.account.cash_percent, threshold=config.CASH_CONSTRAINED_PERCENT, source="decision_context", as_of=context.generated_at))
        return result

    @staticmethod
    def _technical(context: DecisionContext) -> list[EvidenceItem]:
        technical = context.technical
        if not technical:
            return []
        result: list[EvidenceItem] = []
        price, sma20, sma60 = context.quote.price if context.quote else None, technical.sma20, technical.sma60
        if price is not None and sma20 is not None and sma60 is not None:
            if price >= sma20 and price >= sma60:
                result.append(_item("trend.above_sma20", "trend", "positive", .5, "价格高于均线", "当前价格高于 20 日和 60 日均线", value=price, threshold=sma20, source="technical_analysis", as_of=technical.as_of))
            if sma20 >= sma60:
                result.append(_item("trend.sma20_above_sma60", "trend", "positive", .6, "均线结构偏强", "20 日均线高于 60 日均线", value=sma20, threshold=sma60, source="technical_analysis", as_of=technical.as_of))
            if price < sma20 and price < sma60:
                result.append(_item("trend.below_sma20_and_sma60", "trend", "negative", .7, "价格低于均线", "当前价格低于 20 日和 60 日均线", value=price, threshold=sma20, source="technical_analysis", as_of=technical.as_of))
        if technical.drawdown_60d_percent <= config.HIGH_DRAWDOWN_PERCENT:
            result.append(_item("trend.drawdown_60d", "trend", "negative", .6, "60 日回撤较大", f"60 日回撤 {technical.drawdown_60d_percent:.2f}%", value=technical.drawdown_60d_percent, threshold=config.HIGH_DRAWDOWN_PERCENT, source="technical_analysis", as_of=technical.as_of))
        if technical.rsi14 >= config.RSI_HOT:
            result.append(_item("momentum.rsi_hot", "momentum", "uncertain", .5, "RSI 偏热", f"RSI(14) 为 {technical.rsi14:.1f}", value=technical.rsi14, threshold=config.RSI_HOT, source="technical_analysis", as_of=technical.as_of))
        elif technical.rsi14 <= config.RSI_COLD:
            result.append(_item("momentum.rsi_cold", "momentum", "uncertain", .5, "RSI 偏冷", f"RSI(14) 为 {technical.rsi14:.1f}", value=technical.rsi14, threshold=config.RSI_COLD, source="technical_analysis", as_of=technical.as_of))
        result.append(_item("momentum.macd_positive" if technical.macd_histogram > 0 else "momentum.macd_negative" if technical.macd_histogram < 0 else "momentum.macd_neutral", "momentum", "positive" if technical.macd_histogram > 0 else "negative" if technical.macd_histogram < 0 else "neutral", .5 if technical.macd_histogram else .2, "MACD 动能", f"MACD 柱为 {technical.macd_histogram}", value=technical.macd_histogram, threshold=0, source="technical_analysis", as_of=technical.as_of))
        if technical.atr_percent >= config.HIGH_ATR_PERCENT:
            result.append(_item("volatility.atr_high", "volatility", "negative", .5, "ATR 波动偏高", f"ATR/收盘价为 {technical.atr_percent:.2f}%", value=technical.atr_percent, threshold=config.HIGH_ATR_PERCENT, source="technical_analysis", as_of=technical.as_of))
        return result

    @staticmethod
    def _risk(context: DecisionContext) -> list[EvidenceItem]:
        risk = context.risk
        if not risk:
            return []
        result = []
        if risk.historical_downside_probability is not None and risk.historical_downside_probability >= config.HIGH_DOWNSIDE_PROBABILITY_PERCENT:
            result.append(_item("risk.historical_downside_high", "risk", "negative", .7, "历史下行概率偏高", f"历史下行概率为 {risk.historical_downside_probability:.2f}%", value=risk.historical_downside_probability, threshold=config.HIGH_DOWNSIDE_PROBABILITY_PERCENT, source=risk.source, as_of=risk.as_of))
        if risk.annualized_volatility_percent is not None and risk.annualized_volatility_percent >= config.HIGH_ANNUALIZED_VOLATILITY_PERCENT:
            result.append(_item("risk.annualized_volatility_high", "risk", "negative", .7, "年化波动率偏高", f"年化波动率为 {risk.annualized_volatility_percent:.2f}%", value=risk.annualized_volatility_percent, threshold=config.HIGH_ANNUALIZED_VOLATILITY_PERCENT, source=risk.source, as_of=risk.as_of))
        return result

    @staticmethod
    def _market(context: DecisionContext) -> list[EvidenceItem]:
        market = context.market_regime
        if not market or market.status != "ready" or market.regime not in {"supportive", "mixed", "defensive"}:
            return []
        direction = "positive" if market.regime == "supportive" else "negative" if market.regime == "defensive" else "neutral"
        return [_item(f"market.{market.regime}", "market", direction, .6 if market.regime != "mixed" else .3, "市场环境", f"市场环境为 {market.regime}", value=market.regime, source=market.source or "market_regime", as_of=market.as_of, fresh=True)]

    @staticmethod
    def _relative(context: DecisionContext) -> list[EvidenceItem]:
        relative = context.relative_strength
        if not relative or relative.status != "ready":
            return []
        label = relative.label or ""
        evidence_id, direction = ("relative.outperform_20d", "positive") if "强" in label else ("relative.underperform_20d", "negative") if "弱" in label else ("relative.neutral_20d", "neutral")
        return [_item(evidence_id, "relative", direction, .5, "相对强弱", label or "相对强弱中性", value=label, source=relative.source, fresh=True)]

    @staticmethod
    def _events(context: DecisionContext) -> list[EvidenceItem]:
        return [_item(f"event.{event.impact}.{event.event_id}", "event", event.impact, .7 if event.impact in {"positive", "negative"} else .4, event.title, event.summary or event.title, value=event.impact, source=event.source, as_of=event.published_at, fresh=True, source_reference=event.source_reference) for event in context.events]

    @staticmethod
    def _plan(context: DecisionContext) -> list[EvidenceItem]:
        plan, quote = context.trade_plan, context.quote
        if not plan or not quote:
            return []
        result = []
        if plan.is_draft:
            result.append(_item("plan.auto_draft", "plan", "uncertain", .35, "系统已生成交易计划草稿", "草稿用于补齐分析上下文，尚未启用，不会触发开仓或加仓条件；可在之后编辑确认。", source="decision_context", as_of=context.generated_at, fresh=True, rule_id=plan.plan_id))
        for condition in plan.structured_conditions:
            trigger, field, operator, value = condition.get("trigger"), condition.get("field"), condition.get("operator"), condition.get("value")
            if field != "close" or not isinstance(trigger, str):
                continue
            matched = operator == "between" and isinstance(value, list) and len(value) == 2 and float(value[0]) <= quote.price <= float(value[1])
            if matched and trigger in {"entry", "add", "reduce", "exit"}:
                result.append(_item(f"plan.{trigger}_condition_met", "plan", "neutral", .6, "交易计划条件命中", f"计划 {trigger} 条件已按结构化价格区间命中", value=quote.price, threshold=str(value), source="trade_plans", as_of=context.generated_at, rule_id=plan.plan_id))
        return result

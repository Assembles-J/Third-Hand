from app.action_policy import ActionPolicyEngine
from app.decision_context import DecisionContextBuilder
from app.decision_models import EvidenceItem
from app.evidence_engine import EvidenceEngine
from app.storage import PortfolioStore


def _context(tmp_path, *, quote=True, rule_cap=8, plan_conditions=None):
    store = PortfolioStore(tmp_path / "policy.db")
    store.add("holding-1", "600519", "test", 100, 14)
    store.save_available_cash(1000)
    if quote:
        store.save_quotes([{ "symbol": "600519", "price": 10, "currency": "CNY", "source": "test", "as_of": "2026-07-31", "retrieved_at": "2026-07-31T10:00:00+08:00"}])
    store.save_daily_prices("600519", [{"trading_date": f"2026-06-{index + 1:02d}", "open": 11, "close": 10, "high": 12, "low": 9, "source": "test"} for index in range(60)])
    store.save_risk({"symbol": "600519", "as_of": "2026-07-31", "sample_count": 60, "historical_downside_probability": 10, "annualized_volatility_percent": 20, "risk_level": "low"})
    store.save_trade_plan({"id": "plan-1", "symbol": "600519", "horizon": "swing", "thesis": "test", "market_expectation": "test", "catalysts": [], "entry_condition": "entry", "add_condition": "add", "reduce_condition": "reduce", "exit_condition": "exit", "max_position_percent": 15, "risk_budget_percent": 3, "enabled": True, "version": 1, "structured_conditions": plan_conditions or []})
    store.save_personal_rule({"id": "rule-1", "scope": "global", "symbol": None, "max_position_percent": rule_cap, "loss_review_percent": 15, "volatility_review_percent": 50, "enabled": True, "version": 1, "updated_at": "2026-07-31T10:00:00+08:00"})
    return DecisionContextBuilder(store).build("600519")


def test_blocked_data_quality_has_higher_precedence_than_all_other_rules(tmp_path):
    context = _context(tmp_path, quote=False)
    candidates = ActionPolicyEngine().evaluate(context, EvidenceEngine().build(context))

    assert candidates[0].action == "BLOCKED"
    assert "quote.price" in candidates[0].blocked_reasons


def test_position_cap_generates_reduce_before_default_hold(tmp_path):
    context = _context(tmp_path)
    candidates = ActionPolicyEngine().evaluate(context, EvidenceEngine().build(context))

    assert candidates[0].action == "REDUCE"
    assert "position.above_max" in candidates[0].supporting_evidence_ids


def test_empty_position_can_never_generate_reduce_from_risk_evidence(tmp_path):
    context = _context(tmp_path, rule_cap=100).model_copy(update={"position": None})
    evidence = (*EvidenceEngine().build(context), EvidenceItem(
        evidence_id="risk.annualized_volatility_high",
        category="risk",
        direction="negative",
        strength=.9,
        title="synthetic high risk",
        description="no position means this may block OPEN but cannot mean REDUCE",
        source="test",
        fresh=True,
        usage_scope="POLICY",
    ))

    candidates = ActionPolicyEngine().evaluate(context, evidence)

    assert candidates[0].action != "REDUCE"
    assert all(candidate.action != "REDUCE" for candidate in candidates)


def test_open_gate_audit_explains_existing_formal_preconditions(tmp_path):
    context = _context(tmp_path, rule_cap=100).model_copy(update={"position": None})
    evidence = EvidenceEngine().build(context)

    audit = ActionPolicyEngine().open_gate_audit(context, evidence)
    checks = {item["check_id"]: item for item in audit["checks"]}

    assert audit["diagnostic_only"] is True
    assert audit["policy_version"] == ActionPolicyEngine.version
    assert checks["position.absent"]["passed"] is True
    assert checks["quote.available"]["passed"] is True
    assert checks["risk.available"]["passed"] is True
    assert checks["action_gate.open"]["passed"] is False
    assert audit["permission"] == "blocked"
    assert audit["blockers"]


def test_add_requires_every_hard_precondition(tmp_path):
    context = _context(tmp_path, rule_cap=100, plan_conditions=[{"trigger": "add", "field": "close", "operator": "between", "value": [9, 11]}])
    candidates = ActionPolicyEngine().evaluate(context, EvidenceEngine().build(context))

    assert all(candidate.action != "ADD" for candidate in candidates)


def test_research_only_negative_event_cannot_change_policy_action(tmp_path):
    context = _context(tmp_path, rule_cap=100)
    evidence = (*EvidenceEngine().build(context), EvidenceItem(
        evidence_id="event.negative.synthetic",
        category="event",
        direction="negative",
        strength=.95,
        title="synthetic negative event",
        description="must remain research only",
        source="test",
        fresh=True,
        usage_scope="RESEARCH_ONLY",
    ))

    candidates = ActionPolicyEngine().evaluate(context, evidence)
    assert candidates[0].action == "HOLD"
    assert "event.negative.synthetic" not in candidates[0].supporting_evidence_ids

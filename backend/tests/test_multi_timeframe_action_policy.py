from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.atomic_models import AtomicEvidenceSnapshot, AtomicFactRecord, EvidenceAvailabilityRecord
from app.decision_continuity import DecisionContinuityPolicy
from app.decision_semantics import EntryDecision, PositionDecision
from app.timeframe_authority import TimeframeAuthorityPolicy


BEIJING = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 19, 14, 30, tzinfo=BEIJING)


def _fact(timeframe: str, metric: str, value: str, suffix: str) -> AtomicFactRecord:
    return AtomicFactRecord(
        fact_id=f"atomic.intraday.{timeframe}.{metric}.{suffix}",
        symbol="600000",
        market="CN",
        domain="intraday_research",
        dimension=f"intraday_research_{timeframe}",
        metric=f"intraday.{timeframe}.{metric}",
        value=value,
        observed_at=NOW,
        freshness_status="fresh",
        retrieval_freshness="fresh",
        polarity="NEUTRAL_MATERIAL",
        materiality="medium",
        comparison_adequacy="partial",
        confidence=.85,
        provenance_hash=(suffix * 64)[:64],
    )


def _snapshot(states: dict[str, tuple[str, str, str]], availability=None, *, snapshot_hash="1" * 64):
    availability = availability or {"60m": "available", "15m": "available", "5m": "available"}
    facts = []
    for index, timeframe in enumerate(("60m", "15m", "5m"), start=1):
        trend, location, momentum = states.get(timeframe, ("UNKNOWN", "UNKNOWN", "UNKNOWN"))
        suffix = str(index)
        facts.extend((
            _fact(timeframe, "trend_structure", trend, suffix),
            _fact(timeframe, "price_location", location, suffix),
            _fact(timeframe, "momentum", momentum, suffix),
        ))
    return AtomicEvidenceSnapshot(
        version="fixture",
        context_id="context",
        context_input_hash="input",
        symbol="600000",
        market="CN",
        generated_at=NOW,
        facts=tuple(facts),
        availability=tuple(
            EvidenceAvailabilityRecord(
                capability=f"intraday.{timeframe}",
                status=availability[timeframe],
                source_keys=("intraday_price_cache",),
            )
            for timeframe in ("60m", "15m", "5m")
        ),
        conflicts=(),
        snapshot_hash=snapshot_hash,
    )


def _context(*, weekly="up", daily="up", holding=False):
    return SimpleNamespace(
        technical=SimpleNamespace(trend=daily, trend_label=daily, rsi_state="neutral"),
        timeframe_technicals=(SimpleNamespace(timeframe="weekly", trend=weekly),),
        position=SimpleNamespace(quantity=100, entry_episode_id="episode", opened_at="2026-08-01T10:00:00+08:00") if holding else None,
    )


def _supportive_states():
    return {
        "60m": ("UP", "ABOVE_FAST_SLOW", "UP"),
        "15m": ("UP", "ABOVE_FAST_SLOW", "UP"),
        "5m": ("UP", "ABOVE_FAST_SLOW", "UP"),
    }


def test_aligned_intraday_can_confirm_but_never_upgrade_a_wait():
    policy = TimeframeAuthorityPolicy()
    snapshot = _snapshot(_supportive_states())
    buy = EntryDecision(action="BUY", decision_confidence=.8, next_state="ENTRY_PENDING")
    wait = EntryDecision(action="WAIT", decision_confidence=.8, next_state="FLAT")

    confirmed, authority, material = policy.apply(_context(), snapshot, buy)
    still_wait, wait_authority, _ = policy.apply(_context(), snapshot, wait)

    assert confirmed.action == "BUY"
    assert authority.confirmation_state == "CONFIRMED"
    assert authority.conflict_state == "NONE"
    assert material["60m_state"] == "SUPPORTIVE"
    assert still_wait.action == "WAIT"
    assert wait_authority.confirmation_state == "NOT_APPLIED"


def test_missing_or_stale_intraday_never_fabricates_confirmation_and_downgrades_new_risk():
    policy = TimeframeAuthorityPolicy()
    availability = {"60m": "available", "15m": "available", "5m": "stale"}
    snapshot = _snapshot(_supportive_states(), availability)

    entry, authority, _ = policy.apply(
        _context(),
        snapshot,
        EntryDecision(action="BUY", decision_confidence=.9, next_state="ENTRY_PENDING"),
    )
    add, add_authority, _ = policy.apply(
        _context(holding=True),
        snapshot,
        PositionDecision(action="ADD", decision_confidence=.9, next_state="HOLDING"),
    )

    assert entry.action == "WAIT"
    assert entry.next_state == "FLAT"
    assert add.action == "HOLD"
    assert authority.confirmation_state == "UNAVAILABLE"
    assert add_authority.confirmation_state == "UNAVAILABLE"
    assert "timeframe.5m.stale" in authority.reason_codes
    assert "timeframe.new_risk_downgraded" in entry.reason_codes


def test_sixty_minute_weakness_delays_new_risk_but_cannot_create_reduce_or_exit():
    policy = TimeframeAuthorityPolicy()
    states = _supportive_states()
    states["60m"] = ("DOWN", "BELOW_FAST_SLOW", "DOWN")
    snapshot = _snapshot(states)

    entry, authority, _ = policy.apply(
        _context(), snapshot,
        EntryDecision(action="BUY", decision_confidence=.8, next_state="ENTRY_PENDING"),
    )
    hold, _, _ = policy.apply(
        _context(holding=True), snapshot,
        PositionDecision(action="HOLD", decision_confidence=.8, next_state="HOLDING"),
    )
    reduce, _, _ = policy.apply(
        _context(holding=True), snapshot,
        PositionDecision(action="REDUCE", decision_confidence=.8, next_state="REDUCE_PENDING"),
    )
    exit_decision, _, _ = policy.apply(
        _context(holding=True), snapshot,
        PositionDecision(action="EXIT", decision_confidence=.8, next_state="EXIT_PENDING"),
    )

    assert entry.action == "WAIT"
    assert authority.confirmation_state == "CONFLICT"
    assert authority.conflict_state == "LOWER_TIMEFRAME"
    assert "timeframe.60m.weak" in authority.reason_codes
    assert hold.action == "HOLD"
    assert reduce.action == "REDUCE"
    assert exit_decision.action == "EXIT"


def test_lower_timeframe_noise_alone_cannot_reduce_existing_position():
    policy = TimeframeAuthorityPolicy()
    states = {
        "60m": ("UP", "ABOVE_FAST_SLOW", "UP"),
        "15m": ("DOWN", "BELOW_FAST_SLOW", "DOWN"),
        "5m": ("DOWN", "BELOW_FAST_SLOW", "DOWN"),
    }
    snapshot = _snapshot(states)
    hold = PositionDecision(action="HOLD", decision_confidence=.7, next_state="HOLDING")

    result, authority, _ = policy.apply(_context(holding=True), snapshot, hold)

    assert result.action == "HOLD"
    assert authority.confirmation_state == "NOT_APPLIED"
    assert "timeframe.15m_5m.weak" not in result.reason_codes


def test_higher_timeframe_downtrend_cannot_be_overridden_by_bullish_intraday():
    policy = TimeframeAuthorityPolicy()
    snapshot = _snapshot(_supportive_states())
    buy = EntryDecision(action="BUY", decision_confidence=.8, next_state="ENTRY_PENDING")

    result, authority, _ = policy.apply(_context(weekly="down", daily="up"), snapshot, buy)

    assert result.action == "WAIT"
    assert authority.confirmation_state == "CONFLICT"
    assert authority.conflict_state == "HIGHER_TIMEFRAME"
    assert "timeframe.higher_structure_conflict" in result.reason_codes


def test_policy_state_excludes_raw_bar_timestamps_and_hashes():
    policy = TimeframeAuthorityPolicy()
    first = _snapshot(_supportive_states(), snapshot_hash="1" * 64)
    second = _snapshot(_supportive_states(), snapshot_hash="2" * 64)
    decision = EntryDecision(action="BUY", decision_confidence=.8, next_state="ENTRY_PENDING")

    _, first_authority, first_state = policy.apply(_context(), first, decision)
    _, second_authority, second_state = policy.apply(_context(), second, decision)

    assert first_authority.confirmation_state == second_authority.confirmation_state == "CONFIRMED"
    assert first_state == second_state
    serialized = str(first_state)
    assert "source_hash" not in serialized
    assert "as_of" not in serialized
    assert "retrieved" not in serialized


def test_continuity_material_fingerprint_changes_only_when_approved_timeframe_state_changes():
    class Quality:
        status = "ready"
        def model_dump(self, mode="json"):
            return {"status": "ready", "action_gates": []}

    context = SimpleNamespace(
        position=None,
        trade_plan=None,
        quote=None,
        data_quality=Quality(),
        technical=SimpleNamespace(trend="up", trend_label="up", rsi_state="neutral"),
        market_regime=None,
        risk=None,
        events=(),
    )
    baseline_state = {
        "policy_version": "v1", "weekly_state": "UP", "daily_state": "UP",
        "60m_state": "SUPPORTIVE", "15m_state": "SUPPORTIVE", "5m_state": "SUPPORTIVE",
        "confirmation_state": "CONFIRMED", "conflict_state": "NONE",
    }
    changed_state = {**baseline_state, "5m_state": "WEAK", "confirmation_state": "UNCONFIRMED"}

    first = DecisionContinuityPolicy._material_fingerprint(context, timeframe_state=baseline_state)
    same = DecisionContinuityPolicy._material_fingerprint(context, timeframe_state=dict(baseline_state))
    changed = DecisionContinuityPolicy._material_fingerprint(context, timeframe_state=changed_state)

    assert first == same
    assert first != changed
    assert DecisionContinuityPolicy._changed_components(first, changed) == ("timeframe_policy_state",)

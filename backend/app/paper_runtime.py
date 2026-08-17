"""Runtime governance helpers for deterministic paper-decision scheduling.

This module keeps candidate selection, pending-decision execution obligations and
version reuse rules explicit. It does not generate actions or execute trades.
"""
from __future__ import annotations

import json

from app import decision_config as config
from app.candidate_selection import CandidateSelection, select_candidates


def _history_eligible_symbols(store, *, minimum_daily_bars: int = 60, limit: int = 10_000) -> tuple[str, ...]:
    """Return locally history-ready symbols without requiring a cached quote.

    Quote freshness belongs to the later DataQuality/ActionGate boundary. Requiring
    a quote here would make a cold start produce an empty candidate cohort before
    the paper runtime had a chance to refresh market data.
    """
    with store._connect() as connection:  # package-internal read-only adapter
        rows = connection.execute(
            """SELECT symbol
               FROM daily_price_cache
               GROUP BY symbol
               HAVING COUNT(*) >= ?
               ORDER BY symbol ASC
               LIMIT ?""",
            (max(1, minimum_daily_bars), max(1, limit)),
        ).fetchall()
    return tuple(str(row["symbol"]).strip().upper() for row in rows)


def current_candidate_selection(store, *, limit: int, rotation_key: str) -> CandidateSelection:
    """Build the formal paper-decision cohort from the locally history-ready pool.

    Watchlists, hot-sector metadata, price rankings, fund flow and LLM output are
    intentionally unavailable here. Existing paper positions are supplied as a
    safety override and are retained even when they lack 60 ready bars. Current
    quotes are refreshed only after selection and are then governed by freshness
    and action gates.
    """
    eligible = _history_eligible_symbols(store, minimum_daily_bars=60, limit=10_000)
    positions = [str(item["symbol"]) for item in store.paper_account().get("positions", [])]
    return select_candidates(
        eligible,
        position_symbols=positions,
        limit=limit,
        rotation_key=rotation_key,
    )


def _is_current_formal_report(report: dict[str, object], *, policy_version: str) -> bool:
    audit_versions = report.get("audit_versions") or {}
    return bool(
        report.get("policy_version") == policy_version
        and report.get("candidate_selection_version") == config.CANDIDATE_SELECTION_VERSION
        and isinstance(audit_versions, dict)
        and audit_versions.get("execution_policy_version") == config.EXECUTION_POLICY_VERSION
    )


def latest_current_version_decision_report(
    store,
    symbol: str,
    *,
    policy_version: str,
    limit: int = 20,
) -> dict[str, object] | None:
    """Return the latest formal paper report, ignoring newer manual/research reports."""
    for report in store.decision_reports(symbol, limit):
        if _is_current_formal_report(report, policy_version=policy_version):
            return report
    return None


def pending_current_version_decision_symbols(
    store,
    *,
    policy_version: str,
    limit: int = 500,
) -> tuple[str, ...]:
    """Return latest unexecuted formal decisions that remain an execution obligation.

    A due historical DecisionReport must not disappear merely because a new day's
    deterministic rotation chose a different research cohort. Conversely, legacy
    reports from an older policy/candidate/execution regime must never leak into
    the frozen observation ledger. Newer manual/research DecisionReports without
    candidate lineage are ignored rather than masking the latest formal paper
    report.
    """
    with store._connect() as connection:  # package-internal read-only adapter
        rows = connection.execute(
            "SELECT decision_id,symbol,payload,created_at FROM decision_reports ORDER BY created_at DESC LIMIT ?",
            (max(1, limit * 20),),
        ).fetchall()
        executed = {
            str(row["decision_id"])
            for row in connection.execute(
                "SELECT DISTINCT decision_id FROM paper_trading_logs WHERE status='executed' AND decision_id IS NOT NULL"
            ).fetchall()
        }

    latest_formal_by_symbol: dict[str, tuple[str, dict[str, object]]] = {}
    for row in rows:
        symbol = str(row["symbol"]).strip().upper()
        if symbol in latest_formal_by_symbol:
            continue
        try:
            report = json.loads(str(row["payload"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not _is_current_formal_report(report, policy_version=policy_version):
            continue
        latest_formal_by_symbol[symbol] = (str(row["decision_id"]), report)

    pending: list[tuple[str, str]] = []
    for symbol, (decision_id, report) in latest_formal_by_symbol.items():
        if decision_id in executed:
            continue
        generated_at = str(report.get("generated_at") or "")
        pending.append((generated_at, symbol))

    pending.sort(key=lambda item: (item[0], item[1]))
    return tuple(symbol for _, symbol in pending[: max(1, limit)])


def report_matches_current_selection(
    report: dict[str, object],
    selection: CandidateSelection,
    *,
    policy_version: str,
) -> bool:
    """Allow same-interval reuse only when policy and candidate lineage match."""
    return bool(
        _is_current_formal_report(report, policy_version=policy_version)
        and report.get("candidate_selection_version") == selection.selection_version
        and report.get("candidate_pool_hash") == selection.candidate_pool_hash
        and report.get("candidate_rotation_key") == selection.rotation_key
    )


def runtime_scope(
    selection: CandidateSelection,
    *,
    requested_symbols=(),
    pending_symbols=(),
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Separate new-decision cohort from due historical execution obligations.

    ``requested_symbols`` is an execution/market-hours scope only. It can narrow
    formal symbols but can never inject a symbol that the deterministic selector
    or pending-decision queue did not already authorize.
    """
    requested = {
        str(symbol).strip().upper()
        for symbol in requested_symbols
        if str(symbol).strip()
    }
    decision_symbols = tuple(
        symbol for symbol in selection.symbols
        if not requested or symbol in requested
    )
    due_symbols = tuple(
        symbol for symbol in dict.fromkeys(str(item).strip().upper() for item in pending_symbols)
        if symbol and (not requested or symbol in requested)
    )
    runtime_symbols = tuple(dict.fromkeys((*decision_symbols, *due_symbols)))
    return decision_symbols, due_symbols, runtime_symbols


def excluded_requested_symbols(selection: CandidateSelection, *, requested_symbols=(), pending_symbols=()) -> tuple[str, ...]:
    """Return explicit requests that are not authorized by selection or pending due work."""
    requested = tuple(dict.fromkeys(str(item).strip().upper() for item in requested_symbols if str(item).strip()))
    authorized = set(selection.symbols) | {str(item).strip().upper() for item in pending_symbols if str(item).strip()}
    return tuple(symbol for symbol in requested if symbol not in authorized)


def candidate_pool_audit(
    selection: CandidateSelection,
    *,
    requested_symbols=(),
    decision_symbols=(),
    due_symbols=(),
) -> dict[str, object]:
    """Stable run-stage payload explaining exactly how the cohort was selected."""
    requested = tuple(dict.fromkeys(str(item).strip().upper() for item in requested_symbols if str(item).strip()))
    reasons = {
        symbol: selection.audit_for(symbol)["candidate_selection_reason"]
        for symbol in selection.symbols
    }
    ranks = {symbol: selection.audit_for(symbol)["candidate_rank"] for symbol in selection.symbols}
    selected_items = [
        {
            "symbol": symbol,
            "rank": ranks[symbol],
            "reason": reasons[symbol],
        }
        for symbol in selection.symbols
    ]
    return {
        "candidate_selection_version": selection.selection_version,
        "candidate_pool_hash": selection.candidate_pool_hash,
        "rotation_key": selection.rotation_key,
        "eligible_count": selection.eligible_count,
        "requested_limit": selection.requested_limit,
        "selected_count": len(selection.symbols),
        "selection_algorithm": "paper_positions_first_then_sha256_deterministic_rotation",
        "rotation_material": f"{selection.selection_version}|{selection.rotation_key}|<symbol>",
        "selection_independent_of": [
            "watchlist",
            "hot_sector",
            "same_day_price_change",
            "fund_flow",
            "news",
            "llm_output",
        ],
        "selected_symbols": list(selection.symbols),
        "selected_items": selected_items,
        "position_symbols": list(selection.position_symbols),
        "rotated_symbols": list(selection.rotated_symbols),
        "requested_scope": list(requested),
        "decision_symbols": list(decision_symbols),
        "due_execution_symbols": list(due_symbols),
        "candidate_rank": ranks,
        "selection_reason": reasons,
    }

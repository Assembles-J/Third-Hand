"""Historical outcome summaries for saved, source-linked portfolio observations."""
from __future__ import annotations

HORIZONS = (1, 5, 20)


def summarize_calibration(observations, daily_bars, action: str) -> dict[str, object]:
    closes = [(str(bar["trading_date"]), float(bar["close"])) for bar in daily_bars]
    samples = {horizon: [] for horizon in HORIZONS}
    for observation in observations:
        try:
            start = next(index for index, (day, _) in enumerate(closes) if day >= str(observation["entry_date"]))
            entry = float(observation["entry_price"])
        except (StopIteration, TypeError, ValueError):
            continue
        if entry <= 0:
            continue
        for horizon in HORIZONS:
            if start + horizon < len(closes):
                samples[horizon].append(round((closes[start + horizon][1] / entry - 1) * 100, 2))
    aligned = {}
    for horizon, returns in samples.items():
        if not returns:
            aligned[str(horizon)] = {"sample_count": 0, "average_return_percent": None, "rule_alignment_rate_percent": None}
            continue
        expects_downside = action in {"risk_review", "wait_for_confirmation"}
        matches = sum(value <= 0 for value in returns) if expects_downside else sum(value >= 0 for value in returns)
        aligned[str(horizon)] = {
            "sample_count": len(returns),
            "average_return_percent": round(sum(returns) / len(returns), 2),
            "rule_alignment_rate_percent": round(matches / len(returns) * 100, 1),
        }
    return {
        "action": action,
        "definition": "规则一致率：风险复核/等待确认后价格未走强，或观察后价格未走弱的历史占比；不是预测概率。",
        "horizons": aligned,
    }

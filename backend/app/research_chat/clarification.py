from __future__ import annotations
def needs_clarification(context,message):
 # Ask only if the user explicitly seeks a personal action and the shared data is incomplete.
 critical=("买" in message or "卖" in message or "加仓" in message or "减仓" in message) and context.data_quality.status=="blocked"
 return ["你希望研究的持仓期限和可承受的最大损失是多少？"] if critical else []

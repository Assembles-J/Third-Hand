from datetime import datetime

import pandas as pd

from app.market import MarketDataService
from app.time_utils import BEIJING_TIMEZONE


def test_hong_kong_quote_prefers_spot_snapshot():
    service = MarketDataService()
    spot = pd.DataFrame([{
        "代码": "01810",
        "名称": "小米集团-W",
        "最新价": 32.4,
        "涨跌额": 0.6,
        "涨跌幅": 1.89,
        "今开": 31.9,
        "最高": 32.8,
        "最低": 31.7,
        "昨收": 31.8,
        "成交量": 100,
        "成交额": 200,
    }])
    retrieved_at = datetime(2026, 7, 30, 10, 30, tzinfo=BEIJING_TIMEZONE)
    service._frame = lambda market: (spot, retrieved_at, "港股公开快照")

    quote = service._hk_quotes(["01810"])[0]

    assert quote["price"] == 32.4
    assert quote["as_of"] == "2026-07-30"
    assert quote["source"] == "港股公开快照"
    assert "交易时段" in quote["freshness_note"]

# """AKShare 真实上游接口诊断测试。
#
# 运行方式：
#
#     pytest tests/test_akshare.py -s -q
#
# 注意：
# 这些测试会实际访问东方财富、新浪等公开数据源，
# 不适合放进每次都执行的普通 CI 单元测试中。
# """
#
# from __future__ import annotations
#
# import traceback
# from collections.abc import Callable
# from datetime import date, timedelta
#
# import akshare as ak
# import pandas as pd
# import pytest
#
#
# def _date_range(days: int = 30) -> tuple[str, str]:
#     """生成最近一段时间的 AKShare 日期参数。"""
#     end = date.today()
#     start = end - timedelta(days=days)
#
#     return (
#         start.strftime("%Y%m%d"),
#         end.strftime("%Y%m%d"),
#     )
#
#
# def _execute_case(
#     name: str,
#     fetcher: Callable[[], pd.DataFrame],
# ) -> pd.DataFrame:
#     """执行一个真实接口请求，并完整输出原始异常。"""
#     print(f"\n{'=' * 20} {name} {'=' * 20}")
#     print("AKShare version:", getattr(ak, "__version__", "unknown"))
#
#     try:
#         frame = fetcher()
#     except Exception as error:
#         print("请求失败")
#         print("error type:", type(error).__name__)
#         print("error repr:", repr(error))
#         traceback.print_exc()
#
#         pytest.fail(
#             f"{name} 请求失败："
#             f"{type(error).__name__}: {error}",
#             pytrace=False,
#         )
#
#     assert frame is not None, f"{name} 返回了 None"
#     assert isinstance(frame, pd.DataFrame), (
#         f"{name} 返回类型不是 DataFrame，"
#         f"实际类型：{type(frame).__name__}"
#     )
#     assert not frame.empty, f"{name} 返回了空 DataFrame"
#
#     print("请求成功")
#     print("rows:", len(frame.index))
#     print("columns:", list(frame.columns))
#     print(frame.tail(3).to_string())
#
#     return frame
#
#
# def test_a_share_history_600900() -> None:
#     """测试 A 股历史日线：长江电力 600900。"""
#     start_date, end_date = _date_range()
#
#     frame = _execute_case(
#         "A股历史行情 600900",
#         lambda: ak.stock_zh_a_hist(
#             symbol="600900",
#             period="daily",
#             start_date=start_date,
#             end_date=end_date,
#             adjust="qfq",
#         ),
#     )
#
#     required_columns = {"日期", "收盘", "最高", "最低"}
#     assert required_columns.issubset(frame.columns), (
#         f"A股历史行情字段发生变化，"
#         f"缺少字段：{required_columns - set(frame.columns)}"
#     )
#
#
# def test_etf_history_588000() -> None:
#     """测试 ETF 历史日线：科创50 ETF 588000。"""
#     start_date, end_date = _date_range()
#
#     frame = _execute_case(
#         "ETF历史行情 588000",
#         lambda: ak.fund_etf_hist_em(
#             symbol="588000",
#             period="daily",
#             start_date=start_date,
#             end_date=end_date,
#             adjust="qfq",
#         ),
#     )
#
#     required_columns = {"日期", "收盘", "最高", "最低"}
#     assert required_columns.issubset(frame.columns), (
#         f"ETF历史行情字段发生变化，"
#         f"缺少字段：{required_columns - set(frame.columns)}"
#     )
#
#
# def test_hk_history_01810() -> None:
#     """测试港股历史日线：小米集团-W 01810。"""
#     frame = _execute_case(
#         "港股历史行情 01810",
#         lambda: ak.stock_hk_daily(symbol="01810"),
#     )
#
#     required_columns = {"close", "high", "low"}
#     assert required_columns.issubset(frame.columns), (
#         f"港股历史行情字段发生变化，"
#         f"缺少字段：{required_columns - set(frame.columns)}"
#     )
#
#
# def test_a_share_spot() -> None:
#     """测试 A 股全市场实时快照。"""
#     frame = _execute_case(
#         "A股实时全市场快照",
#         ak.stock_zh_a_spot_em,
#     )
#
#     assert "代码" in frame.columns, (
#         f"A股实时接口字段发生变化，"
#         f"当前字段：{list(frame.columns)}"
#     )
#
#     matched = frame[
#         frame["代码"].astype(str).str.zfill(6) == "600900"
#     ]
#
#     assert not matched.empty, "全市场快照中未找到 600900"
#
#
# def test_etf_spot() -> None:
#     """测试 ETF 全市场实时快照。"""
#     frame = _execute_case(
#         "ETF实时全市场快照",
#         ak.fund_etf_spot_em,
#     )
#
#     assert "代码" in frame.columns, (
#         f"ETF实时接口字段发生变化，"
#         f"当前字段：{list(frame.columns)}"
#     )
#
#     matched = frame[
#         frame["代码"].astype(str).str.zfill(6) == "588000"
#     ]
#
#     assert not matched.empty, "ETF快照中未找到 588000"
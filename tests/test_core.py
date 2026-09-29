# -*- coding: utf-8 -*-
"""核心算法与涨停规则测试（无需联网）。运行：pytest -q"""
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from nboard import core, rules  # noqa: E402


# ---------------- rules ----------------
def test_limit_rate_by_board():
    assert rules.limit_rate('600000.XSHG', '2024-01-01') == 0.10
    assert rules.limit_rate('000001.XSHE', '2024-01-01') == 0.10
    assert rules.limit_rate('688001.XSHG', '2024-01-01') == 0.20
    assert rules.limit_rate('300001.XSHE', '2024-01-01') == 0.20
    assert rules.limit_rate('300001.XSHE', '2019-01-01') == 0.10   # 创业板 2020-08-24 前
    assert rules.limit_rate('830001.BJSE', '2024-01-01') == 0.30
    assert rules.limit_rate('600000.XSHG', '2024-01-01', is_st=True) == 0.05


def test_limit_price_rounding():
    assert rules.limit_price(10.00, '600000.XSHG', '2024-01-01') == 11.00
    assert rules.limit_price(10.05, '600000.XSHG', '2024-01-01') == 11.06   # round(11.055)->11.06
    assert rules.limit_price(2.00, '600000.XSHG', '2024-01-01') == 2.20
    assert np.isnan(rules.limit_price(float('nan'), '600000.XSHG', '2024-01-01'))


# ---------------- board_mask ----------------
def _lu(vals):
    idx = pd.bdate_range('2024-01-01', periods=len(vals))
    return pd.DataFrame({'A': vals}, index=idx).astype(bool)


def test_board_mask_levels():
    lu = _lu([False, False, True, True, True, False, False])  # day2,3,4 三连板
    assert list(core.board_mask(lu, 1).iloc[:, 0]) == [False, False, True, False, False, False, False]
    assert list(core.board_mask(lu, 2).iloc[:, 0]) == [False, False, False, True, False, False, False]
    assert list(core.board_mask(lu, 3).iloc[:, 0]) == [False, False, False, False, True, False, False]
    # 至少 N 板
    assert list(core.board_mask(lu, 2, exact=False).iloc[:, 0]) == [False, False, False, True, True, False, False]


# ---------------- compute_records ----------------
def _wide(vals, cols):
    idx = pd.bdate_range('2024-01-01', periods=len(vals[cols[0]]))
    return pd.DataFrame(vals, index=idx, columns=cols)


def test_compute_with_high_limit_false_positive_and_resume():
    cols = ['600000', '600001', '600002']
    close = pd.DataFrame(index=pd.bdate_range('2024-01-01', periods=7), columns=cols, dtype=float)
    hl = pd.DataFrame(index=close.index, columns=cols, dtype=float)
    paused = pd.DataFrame(False, index=close.index, columns=cols)
    # X: day2 真涨停(=涨停价11)，day3 停牌 -> 样本剔除
    close['600000'] = [10, 10, 11.0, 10.5, 10.6, 10.7, 10.8]
    hl['600000'] = [11, 11, 11.0, 11.55, 11.66, 11.77, 11.88]
    paused.loc[close.index[3], '600000'] = True
    # Y: day2 收 10.96(+9.6%) 未封板 -> 不算涨停；day3 才涨停
    close['600001'] = [10, 10, 10.96, 11.0, 10.5, 10.6, 10.7]
    hl['600001'] = [11, 11, 11.0, 11.0, 11.55, 11.66, 11.77]
    # Z: day1 停牌，day2 复牌涨停
    close['600002'] = [10, np.nan, 11.0, 10.5, 10.6, 10.7, 10.8]
    hl['600002'] = [11, np.nan, 11.0, 11.55, 11.66, 11.77, 11.88]
    paused.loc[close.index[1], '600002'] = True

    recs = core.compute_records(close, close, close, 1, '2024-01-01', '2024-12-31', 1,
                                high_limit=hl, paused=paused)
    got = {r['code']: r for r in recs}
    assert '600000' not in got            # T+1 停牌 -> 剔除
    assert got['600001']['last_date'] == '20240104'   # day2 未封板，day3 才是首板
    assert got['600002']['last_date'] == '20240103'   # 复牌涨停被识别


def test_compute_basic_returns():
    idx = pd.bdate_range('2024-01-01', periods=8)
    cols = ['600000']
    close = pd.DataFrame({'600000': [10.0, 10, 11, 12.1, 12, 11.5, 11.2, 11.0]}, index=idx)
    open_ = close.copy(); high = close.copy()
    open_.loc[idx[3], '600000'] = 11.5
    high.loc[idx[3], '600000'] = 12.3
    hl = pd.DataFrame({'600000': [11, 11, 11, 11.55, 12.1, 12.1, 12.1, 12.1]}, index=idx)
    recs = core.compute_records(open_, high, close, 1, '2024-01-01', '2024-12-31', 1, high_limit=hl)
    r = recs[0]
    assert r['n_events'] == 1 and r['last_date'] == '20240103'
    assert round(r['open_ret'][0], 2) == 4.55
    assert round(r['high_ret'][0], 2) == 11.82
    assert round(r['close_ret'][0], 2) == 10.00


def test_fallback_without_high_limit():
    idx = pd.bdate_range('2024-01-01', periods=8)
    close = pd.DataFrame({'600000': [10.0, 10, 11, 12.1, 12, 11.5, 11.2, 11.0]}, index=idx)
    recs = core.compute_records(close, close, close, 1, '2024-01-01', '2024-12-31', 1,
                                high_limit=None)
    assert recs[0]['n_events'] == 1   # 11/10-1=10% >= 9.5%

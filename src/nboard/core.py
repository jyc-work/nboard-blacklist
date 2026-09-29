# -*- coding: utf-8 -*-
"""数据源无关的核心算法：N 板掩码 + T+1 三档收益统计。"""
import numpy as np
import pandas as pd

from . import rules

_TWENTY_CM = ('300', '301', '688', '689')


def board_mask(is_lu, level, exact=True):
    """第 N 板掩码。level=1 即首板。

    exact=True : T 及前 N-1 日连续涨停，且 T-N 日未涨停（恰好第 N 板）。
    exact=False: T 起向前连续涨停 >= N 天（至少 N 板）。
    """
    m = is_lu.copy()
    for k in range(1, level):
        m = m & (is_lu.shift(k) == True)
    if exact:
        m = m & (is_lu.shift(level) != True)
    return m


def is_limit_up(close, high_limit, tol=1e-3):
    """用交易所涨停价判定封板；high_limit 为 NaN 处返回 False。"""
    return close.ge(high_limit - tol)


def _fallback_is_lu(close):
    """无 high_limit 时的回退：涨跌幅阈值近似（主板 9.5% / 双创 19.5%）。"""
    thr = pd.Series(
        {c: (0.195 if str(c).split('.')[0].startswith(_TWENTY_CM) else 0.095)
         for c in close.columns})
    prev = close.ffill().shift(1)          # 停牌日取停牌前最后价，避免复牌漏判
    return (close / prev - 1.0).ge(thr, axis=1)


def compute_records(open_, high, close, level, start, end, min_sample,
                    high_limit=None, paused=None, exact=True, tol=1e-3):
    """返回每只票的 n_events / n_valid / 三档收益数组 / 最近日期。

    open_/high/close/high_limit/paused: date × code 宽表（同一索引与列）。
    """
    if high_limit is not None:
        is_lu = is_limit_up(close, high_limit, tol)
        if paused is not None:                      # 停牌日不可能是涨停
            is_lu = is_lu & (~(paused == True))
    else:
        is_lu = _fallback_is_lu(close)

    board = board_mask(is_lu, level, exact)
    d0, d1 = pd.Timestamp(start), pd.Timestamp(end)
    board = board.loc[(board.index >= d0) & (board.index <= d1)].fillna(False)

    open_ret = ((open_.shift(-1) / close - 1.0) * 100).loc[board.index]
    high_ret = ((high.shift(-1) / close - 1.0) * 100).loc[board.index]
    close_ret = ((close.shift(-1) / close - 1.0) * 100).loc[board.index]
    paused_next = (paused.shift(-1) == True).loc[board.index] if paused is not None else None

    out = []
    for c in close.columns:
        m = board[c].values.astype(bool)
        if not m.any():
            continue
        oc = open_ret[c].values[m]
        hc = high_ret[c].values[m]
        cc = close_ret[c].values[m]
        valid = ~np.isnan(cc)
        if paused_next is not None:
            valid = valid & (~paused_next[c].values[m])
        if int(valid.sum()) < min_sample:
            continue
        dates = board.index[m]
        out.append({
            'code': c,
            'n_events': int(m.sum()),
            'n_valid': int(valid.sum()),
            'open_ret': oc[valid],
            'high_ret': hc[valid],
            'close_ret': cc[valid],
            'last_date': dates[-1].strftime('%Y%m%d'),
        })
    return out


def _prob(arr):
    a = arr[~np.isnan(arr)]
    return float((a > 0).sum()) / len(a) * 100 if len(a) else 0.0


def judge_black(avg_open, avg_close, basis='close'):
    if basis == 'open':
        return avg_open < 0
    if basis == 'both':
        return (avg_open < 0) and (avg_close < 0)
    if basis == 'any':
        return (avg_open < 0) or (avg_close < 0)
    return avg_close < 0


def summarize(records, level, names=None, industries=None, basis='close'):
    """records -> 全量统计 DataFrame（含是否黑名单列）。"""
    names = names or {}
    industries = industries or {}
    label = '%d板' % level
    rows = []
    for r in records:
        o, h, c = r['open_ret'], r['high_ret'], r['close_ret']
        avg_o = float(np.nanmean(o)) if len(o) else float('nan')
        avg_h = float(np.nanmean(h)) if len(h) else float('nan')
        avg_c = float(np.mean(c))
        rows.append({
            '股票代码': r['code'],
            '股票名称': names.get(r['code'], ''),
            '所属板块': rules.board_name(r['code']),
            '概念': industries.get(r['code'], ''),
            '%s次数' % label: r['n_events'],
            '有效样本数': r['n_valid'],
            '平均开盘收益率(%)': round(avg_o, 2) if not np.isnan(avg_o) else '',
            '平均最高收益率(%)': round(avg_h, 2) if not np.isnan(avg_h) else '',
            '平均收盘收益率(%)': round(avg_c, 2),
            '高开概率(%)': round(_prob(o), 2),
            '最高价高于%s收盘概率(%%)' % label: round(_prob(h), 2),
            '收盘上涨概率(%)': round(_prob(c), 2),
            '亏损次数占比(%)': round(float((c < 0).sum()) / len(c) * 100, 2),
            '最近%s日期' % label: r['last_date'],
            '是否黑名单': '是' if judge_black(avg_o, avg_c, basis) else '否',
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values('平均收盘收益率(%)', ascending=True)


ALL_COLS = lambda level: [
    '股票代码', '股票名称', '所属板块', '概念', '%d板次数' % level, '有效样本数',
    '平均开盘收益率(%)', '平均最高收益率(%)', '平均收盘收益率(%)',
    '高开概率(%)', '最高价高于%d板收盘概率(%%)' % level, '收盘上涨概率(%)',
    '亏损次数占比(%)', '最近%d板日期' % level, '是否黑名单']

BLACK_COLS = lambda level: [
    '股票代码', '股票名称', '所属板块', '概念',
    '平均开盘收益率(%)', '平均最高收益率(%)', '平均收盘收益率(%)',
    '有效样本数', '亏损次数占比(%)', '最近%d板日期' % level]

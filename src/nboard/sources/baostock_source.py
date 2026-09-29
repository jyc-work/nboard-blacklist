# -*- coding: utf-8 -*-
"""Baostock 数据源（免费、无 token，不走 HTTP 代理）。

baostock 自带 preclose / tradestatus / isST 字段，可精确算涨停价、识别停牌。
代码格式为 'sh.600000' / 'sz.000001' / 'bj.830001'。
"""
import pandas as pd

from .. import rules

try:
    import baostock as bs
except ImportError:
    bs = None

_FIELDS = ('open', 'high', 'close', 'high_limit', 'paused')
_logged_in = False


def available():
    return bs is not None


def _bt_code(code):
    c = str(code).split('.')[0].zfill(6)
    if c.startswith(('6', '9')):
        return 'sh.' + c
    if c.startswith(('4', '8')):
        return 'bj.' + c
    return 'sz.' + c


def to_full_code(code):
    return _bt_code(code).split('.')[1] + '.' + _bt_code(code).split('.')[0].upper()


def _login():
    global _logged_in
    if not _logged_in:
        res = bs.login()
        if res.error_code != '0':
            raise RuntimeError('baostock 登录失败：%s' % res.error_msg)
        _logged_in = True


def get_pool(day, exclude_st=True, exclude_chinext=True, exclude_kcb=True,
             exclude_bse=True, max_stocks=None):
    _login()
    rs = bs.query_all_stock(day=day)
    pool = {}
    while rs.error_code == '0' and rs.next():
        row = dict(zip(rs.fields, rs.get_row_data()))
        code = row['code'].split('.')[1]          # 6 位
        name = row.get('code_name', '')
        if exclude_st and ('ST' in name or '退' in name):
            continue
        if exclude_kcb and code.startswith(('688', '689')):
            continue
        if exclude_bse and code.startswith(('4', '8', '92')):
            continue
        if exclude_chinext and code.startswith(('300', '301')):
            continue
        pool[to_full_code(code)] = name
        if max_stocks and len(pool) >= max_stocks:
            break
    return pool


def get_daily(codes, start, end, cache_dir=None, progress=True):
    _login()
    import os
    frames = []
    for i, code in enumerate(codes):
        full = to_full_code(code)
        path = os.path.join(cache_dir, '%s_%s_%s.csv' % (full, start, end)) if cache_dir else None
        if path and os.path.exists(path):
            frames.append(pd.read_csv(path, parse_dates=['time']))
            continue
        rs = bs.query_history_k_data_plus(
            _bt_code(code),
            'date,open,high,low,close,preclose,volume,tradestatus,isST',
            start_date=start, end_date=end, frequency='d', adjustflag='3')
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=rs.fields)
        df = df.rename(columns={'date': 'time'})
        for c in ('open', 'high', 'close', 'preclose', 'volume'):
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').reset_index(drop=True)
        df['high_limit'] = [rules.limit_price(p, code, d, is_st=(s == '1'))
                            for p, d, s in zip(df['preclose'], df['time'].dt.date, df['isST'])]
        df['paused'] = (df['tradestatus'] == '0')
        df['code'] = full
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            df.to_csv(path, index=False)
        frames.append(df[['time', 'code', 'open', 'high', 'close', 'high_limit', 'paused']])
        if progress and (i + 1) % 100 == 0:
            print('  已取 %d/%d' % (i + 1, len(codes)))
    if not frames:
        return None
    long = pd.concat(frames, ignore_index=True)
    out = {}
    for f in _FIELDS:
        d = long[['time', 'code', f]].drop_duplicates(subset=['time', 'code'])
        out[f] = d.pivot(index='time', columns='code', values=f)
    return out

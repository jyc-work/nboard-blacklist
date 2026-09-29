# -*- coding: utf-8 -*-
"""AKShare 数据源（免费、无 token，默认后端）。

注意：AKShare 无交易所涨停价字段，这里用「不复权前收 + 板块规则」自行计算
high_limit，因此默认 adjust=''（不复权），保证涨停判定精确；T+1 收益也在不复权
价上计算，除权日会有少量噪声（见 README 局限）。
"""
import os
import time

import pandas as pd

from .. import rules

try:
    import akshare as ak
except ImportError:  # 允许只用其它后端
    ak = None

_RENAME = {'日期': 'time', '开盘': 'open', '收盘': 'close', '最高': 'high', '成交量': 'volume'}
_FIELDS = ('open', 'high', 'close', 'high_limit', 'paused')


def to_full_code(code):
    """6 位代码 -> 带交易所后缀，避免 CSV/Excel 丢前导零。"""
    c = str(code).split('.')[0].zfill(6)
    if c.startswith(('6', '9')):
        return c + '.SH'
    if c.startswith(('4', '8')):
        return c + '.BJ'
    return c + '.SZ'


def available():
    return ak is not None


def get_pool(exclude_st=True, exclude_chinext=True, exclude_kcb=True,
             exclude_bse=True, max_stocks=None):
    """返回 {code6: name} 字典。"""
    if ak is None:
        raise RuntimeError('未安装 akshare：pip install akshare')
    try:
        df = ak.stock_info_a_code_name()          # code, name
        df = df.rename(columns={'code': 'code', 'name': 'name'})
    except Exception:
        df = ak.stock_zh_a_spot_em().rename(columns={'代码': 'code', '名称': 'name'})[['code', 'name']]
    pool = {}
    for _, r in df.iterrows():
        code = str(r['code']).zfill(6)
        name = str(r['name'])
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


def _fetch_one(code, start, end, adjust, cache_dir, sleep):
    code6 = str(code).split('.')[0]
    full = to_full_code(code)
    if cache_dir:
        key = '%s_%s_%s_%s.csv' % (full, start, end, adjust or 'raw')
        path = os.path.join(cache_dir, key)
        if os.path.exists(path):
            return pd.read_csv(path, parse_dates=['time'])
    raw = ak.stock_zh_a_hist(symbol=code6, period='daily',
                             start_date=start.replace('-', ''),
                             end_date=end.replace('-', ''), adjust=adjust)
    if raw is None or raw.empty:
        return None
    cols = [c for c in _RENAME if c in raw.columns]
    df = raw.rename(columns=_RENAME)[[v for v in (_RENAME[c] for c in cols)]].copy()
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    # 前收 -> 涨停价（用同一口径的价格序列，停牌日 AKShare 会直接缺行，shift 即最后成交价）
    pre = df['close'].shift(1)
    df['high_limit'] = [rules.limit_price(p, code6, d)
                        for p, d in zip(pre, df['time'].dt.date)]
    df['paused'] = df.get('volume', pd.Series(0, index=df.index)).fillna(0) <= 0
    df['code'] = full
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        df.to_csv(os.path.join(cache_dir, '%s_%s_%s_%s.csv'
                               % (full, start, end, adjust or 'raw')), index=False)
    if sleep:
        time.sleep(sleep)
    return df


def _to_wide(long):
    out = {}
    for f in _FIELDS:
        d = long[['time', 'code', f]].drop_duplicates(subset=['time', 'code'])
        out[f] = d.pivot(index='time', columns='code', values=f)
    return out


def get_daily(codes, start, end, adjust='', cache_dir=None, sleep=0.2, progress=True):
    """codes: 6 位代码列表 -> 宽表字典。"""
    if ak is None:
        raise RuntimeError('未安装 akshare：pip install akshare')
    frames = []
    for i, code in enumerate(codes):
        try:
            df = _fetch_one(code, start, end, adjust, cache_dir, sleep)
        except Exception as ex:
            if progress:
                print('  [warn] %s 取数失败：%s' % (code, ex))
            df = None
        if df is not None and not df.empty:
            frames.append(df)
        if progress and (i + 1) % 100 == 0:
            print('  已取 %d/%d' % (i + 1, len(codes)))
    if not frames:
        return None
    return _to_wide(pd.concat(frames, ignore_index=True))

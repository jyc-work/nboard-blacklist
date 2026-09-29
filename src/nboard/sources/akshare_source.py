# -*- coding: utf-8 -*-
"""AKShare 数据源（免费、无 token）。

东方财富接口在部分网络/安全软件下会被定向重置，因此这里做**多通道回退**：
    新浪 (stock_zh_a_daily) -> 腾讯 (stock_zh_a_hist_tx) -> 东财 (stock_zh_a_hist)

无交易所涨停价字段，用「不复权前收 + 板块规则」自行计算 high_limit，故默认
adjust=''（不复权）以保证涨停判定精确；除权日收益有少量噪声（见 README 局限）。
"""
import os
import time

import pandas as pd

from .. import rules

try:
    import akshare as ak
except ImportError:
    ak = None

_FIELDS = ('open', 'high', 'close', 'high_limit', 'paused')


def available():
    return ak is not None


def to_full_code(code):
    """6 位代码 -> 带交易所后缀，避免 CSV/Excel 丢前导零。"""
    c = str(code).split('.')[0].zfill(6)
    if c.startswith(('6', '9')):
        return c + '.SH'
    if c.startswith(('4', '8')):
        return c + '.BJ'
    return c + '.SZ'


def _prefixed(code6):
    c = str(code6).split('.')[0]
    if c.startswith(('6', '9')):
        return 'sh' + c
    if c.startswith(('4', '8')):
        return 'bj' + c
    return 'sz' + c


def get_pool(exclude_st=True, exclude_chinext=True, exclude_kcb=True,
             exclude_bse=True, max_stocks=None):
    if ak is None:
        raise RuntimeError('未安装 akshare：pip install akshare')
    try:
        df = ak.stock_info_a_code_name()          # code, name
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


def _norm(df, code6, full, adjust):
    df = df.rename(columns={'date': 'time'})
    if 'volume' not in df.columns and 'amount' in df.columns:
        df = df.rename(columns={'amount': 'volume'})
    keep = [c for c in ('time', 'open', 'high', 'close', 'volume') if c in df.columns]
    df = df[keep].copy()
    df['time'] = pd.to_datetime(df['time'])
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    else:
        df['volume'] = 1.0
    df = df.sort_values('time').reset_index(drop=True)
    if adjust:                       # 复权价无法用原始涨停价，退回比值法（高阈值）
        pre = df['close'].shift(1)
        df['high_limit'] = pre * 1.099          # 近似：主板阈值；仅复权模式使用
    else:
        pre = df['close'].shift(1)
        df['high_limit'] = [rules.limit_price(p, code6, d)
                            for p, d in zip(pre, df['time'].dt.date)]
    df['paused'] = df['volume'].fillna(0) <= 0
    df['code'] = full
    return df


def _fetch_one(code, start, end, adjust, method, sleep):
    code6 = str(code).split('.')[0]
    full = to_full_code(code)
    s, e = start.replace('-', ''), end.replace('-', '')
    errs = []

    def sina():
        return ak.stock_zh_a_daily(symbol=_prefixed(code6), start_date=s, end_date=e, adjust=adjust)

    def tx():
        return ak.stock_zh_a_hist_tx(symbol=_prefixed(code6), start_date=s, end_date=e, adjust=adjust)

    def em():
        return ak.stock_zh_a_hist(symbol=code6, period='daily', start_date=s, end_date=e, adjust=adjust)

    methods = {'sina': sina, 'tx': tx, 'em': em}
    order = [method] if method in methods else ['sina', 'tx', 'em']
    for name in order:
        try:
            raw = methods[name]()
            if raw is not None and not raw.empty:
                if sleep:
                    time.sleep(sleep)
                return _norm(raw, code6, full, adjust)
        except Exception as ex:
            errs.append('%s:%s' % (name, type(ex).__name__))
    if errs:
        raise RuntimeError(' / '.join(errs))
    return None


def _to_wide(long):
    out = {}
    for f in _FIELDS:
        d = long[['time', 'code', f]].drop_duplicates(subset=['time', 'code'])
        out[f] = d.pivot(index='time', columns='code', values=f)
    return out


def get_daily(codes, start, end, adjust='', cache_dir=None, sleep=0.3,
              method='auto', progress=True):
    """codes -> 宽表字典。method: auto / sina / tx / em。"""
    if ak is None:
        raise RuntimeError('未安装 akshare：pip install akshare')
    frames = []
    for i, code in enumerate(codes):
        full = to_full_code(code)
        path = os.path.join(cache_dir, '%s_%s_%s_%s.csv' % (full, start, end, adjust or 'raw')) \
            if cache_dir else None
        if path and os.path.exists(path):
            frames.append(pd.read_csv(path, parse_dates=['time']))
        else:
            try:
                df = _fetch_one(code, start, end, adjust, method, sleep)
            except Exception as ex:
                if progress:
                    print('  [warn] %s 取数失败：%s' % (full, ex))
                df = None
            if df is not None and not df.empty:
                if cache_dir:
                    os.makedirs(cache_dir, exist_ok=True)
                    df.to_csv(path, index=False)
                frames.append(df)
        if progress and (i + 1) % 100 == 0:
            print('  已取 %d/%d' % (i + 1, len(codes)))
    if not frames:
        return None
    return _to_wide(pd.concat(frames, ignore_index=True))

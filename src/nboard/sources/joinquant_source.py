# -*- coding: utf-8 -*-
"""聚宽数据源（在研究环境 / 回测中运行）。

聚宽提供精确的交易所涨停价 high_limit 与停牌标记 paused，无需自己算规则。
"""
import pandas as pd

try:  # 仅在聚宽环境可用
    from jqdata import get_price, get_all_securities, get_industries, get_industry_stocks
except Exception:
    get_price = get_all_securities = get_industries = get_industry_stocks = None

_FIELDS = ('open', 'high', 'close', 'high_limit', 'paused')


def available():
    return get_price is not None


def _to_wide(df, value):
    df = df[['time', 'code', value]].drop_duplicates(subset=['time', 'code'])
    return df.pivot(index='time', columns='code', values=value)


def _get_price(codes, start, end, field):
    try:
        return get_price(codes, start_date=start, end_date=end, frequency='daily',
                         fields=[field], fq='pre', panel=False,
                         skip_paused=False, fill_paused=False)
    except TypeError:  # 旧版无 fill_paused
        return get_price(codes, start_date=start, end_date=end, frequency='daily',
                         fields=[field], fq='pre', panel=False, skip_paused=False)


def get_pool(exclude_st=True, exclude_chinext=True, exclude_kcb=True,
             exclude_bse=True, max_stocks=None):
    sec = get_all_securities(types=['stock']).copy()
    sec['start_date'] = pd.to_datetime(sec['start_date'])
    sec['end_date'] = pd.to_datetime(sec['end_date'])
    pool = {}
    for code, row in sec.iterrows():
        name = row['display_name']
        if exclude_st and ('ST' in name or '退' in name):
            continue
        if exclude_kcb and code.startswith(('688', '689')):
            continue
        if exclude_bse and code.startswith(('4', '8', '92')):
            continue
        if exclude_chinext and code.startswith(('300', '301')):
            continue
        pool[code] = name
        if max_stocks and len(pool) >= max_stocks:
            break
    return pool


def get_daily(codes, start, end, chunk=400, progress=True):
    out = {}
    for f in _FIELDS:
        frames = []
        for i in range(0, len(codes), chunk):
            part = list(codes[i:i + chunk])
            try:
                df = _get_price(part, start, end, f)
            except Exception as ex:
                if progress:
                    print('  [warn] %s 取数失败：%s' % (f, ex))
                return None
            if df is not None and not df.empty:
                frames.append(df)
        out[f] = _to_wide(pd.concat(frames, ignore_index=True), f) if frames else None
        if progress:
            print('  字段 %s 完成' % f)
    return out


def get_industry_map(codes, date):
    m = {}
    if get_industries is None:
        return m
    try:
        for icode, row in get_industries(name='sw_l1', date=date).iterrows():
            iname = row.get('industry_name') or row.get('name') or str(icode)
            for s in get_industry_stocks(icode, date=date):
                m[s] = iname
    except Exception as ex:
        print('行业映射失败：%s' % ex)
    return m

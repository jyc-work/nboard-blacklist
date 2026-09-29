# -*- coding: utf-8 -*-
"""A 股涨跌停规则（按板块 / ST / 历史变更）。

这是整个项目最容易算错、也最有价值的部分：
- 主板 10%，创业板/科创板 20%，北交所 30%，ST 5%；
- 创业板 20% 自 2020-08-24 起（此前 10%）；
- 涨停价 = round(前收 × (1 + 幅度), 2)，A 股四舍五入到分。
"""
from datetime import date, datetime

CHINEXT_20_FROM = date(2020, 8, 24)   # 创业板涨跌幅改 20% 的日期
BSE_OPEN = date(2021, 11, 15)         # 北交所开市


def to_date(d):
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], '%Y-%m-%d').date()


def board_of(code):
    """6 位代码（可带 .XSHE/.XSHG 后缀）-> 板块。"""
    c = str(code).split('.')[0]
    if c.startswith(('300', '301')):
        return 'chinext'
    if c.startswith(('688', '689')):
        return 'star'
    if c.startswith(('4', '8', '92')):
        return 'bse'
    return 'main'


def board_name(code):
    return {'chinext': '创业板', 'star': '科创板', 'bse': '北交所', 'main': '主板'}[board_of(code)]


def limit_rate(code, d, is_st=False):
    """当日涨停幅度（小数）。"""
    b = board_of(code)
    dd = to_date(d)
    if b == 'bse':
        return 0.30
    if b == 'star':
        return 0.20
    if b == 'chinext':
        return 0.20 if dd >= CHINEXT_20_FROM else 0.10
    return 0.05 if is_st else 0.10


def limit_price(pre_close, code, d, is_st=False):
    """涨停价。pre_close 无效时返回 NaN。"""
    try:
        p = float(pre_close)
    except (TypeError, ValueError):
        return float('nan')
    if p != p or p <= 0:
        return float('nan')
    r = limit_rate(code, d, is_st)
    return round(p * (1 + r) + 1e-8, 2)

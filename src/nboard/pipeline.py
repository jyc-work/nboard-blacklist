# -*- coding: utf-8 -*-
"""串起 数据源 -> 核心算法 -> CSV 输出 的流水线。"""
import os

import pandas as pd

from . import core, io


def run_pipeline(pool, daily, level, start, end, min_sample=3, basis='close',
                 exact=True, industries=None, out_dir='.', out_prefix=''):
    """pool: {code: name}；daily: 宽表字典。返回 (全量路径, 黑名单路径)。"""
    records = core.compute_records(
        daily['open'], daily['high'], daily['close'], level, start, end, min_sample,
        high_limit=daily.get('high_limit'), paused=daily.get('paused'), exact=exact)
    df = core.summarize(records, level, names=pool, industries=industries, basis=basis)
    if df.empty:
        return None, None
    tag = '%s_%s' % (start.replace('-', ''), end.replace('-', ''))
    all_path = io.write_csv(
        os.path.join(out_dir, '%s全量统计_%d板_%s.csv' % (out_prefix, level, tag)),
        df[core.ALL_COLS(level)])
    black = df[df['是否黑名单'] == '是']
    black_path = None
    if not black.empty:
        black_path = io.write_csv(
            os.path.join(out_dir, '%s黑名单_%d板_%s.csv' % (out_prefix, level, tag)),
            black[core.BLACK_COLS(level)])
    return all_path, black_path


def fetch_start(start, level, buffer_days=None):
    if buffer_days is None:
        buffer_days = 15 + level * 3
    return (pd.Timestamp(start) - pd.Timedelta(days=buffer_days)).strftime('%Y-%m-%d')

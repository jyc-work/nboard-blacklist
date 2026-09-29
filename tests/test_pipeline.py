# -*- coding: utf-8 -*-
"""流水线离线冒烟测试：合成宽表 -> 统计 -> CSV。"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from nboard import pipeline  # noqa: E402


def _daily():
    idx = pd.bdate_range('2024-01-01', periods=8)
    cols = ['600000', '600001']
    close = pd.DataFrame({
        '600000': [10.0, 10, 11, 12.1, 12, 11.5, 11.2, 11.0],
        '600001': [10.0, 10, 10, 10.0, 10.4, 10.2, 10.1, 10.0],
    }, index=idx)
    open_ = close.copy(); high = close.copy()
    open_.loc[idx[3], '600000'] = 11.5
    high.loc[idx[3], '600000'] = 12.3
    hl = pd.DataFrame({
        '600000': [11, 11, 11, 11.55, 12.1, 12.1, 12.1, 12.1],
        '600001': [11, 11, 11, 11, 11, 11, 11, 11],
    }, index=idx).astype(float)
    paused = pd.DataFrame(False, index=idx, columns=cols)
    return {'open': open_, 'high': high, 'close': close, 'high_limit': hl, 'paused': paused}


def test_pipeline_writes_csv(tmp_path):
    pool = {'600000': '甲', '600001': '乙'}
    all_path, black_path = pipeline.run_pipeline(
        pool, _daily(), 1, '2024-01-01', '2024-12-31', min_sample=1,
        out_dir=str(tmp_path))
    assert all_path and os.path.exists(all_path)
    df = pd.read_csv(all_path, encoding='utf-8-sig', dtype={'股票代码': str})
    assert '1板次数' in df.columns
    assert '是否黑名单' in df.columns
    assert set(['平均开盘收益率(%)', '平均最高收益率(%)', '平均收盘收益率(%)']).issubset(df.columns)
    # 600000 首板 T+1 +10% -> 非黑名单
    r = df[df['股票代码'] == '600000'].iloc[0]
    assert r['平均收盘收益率(%)'] == 10.0 and r['是否黑名单'] == '否'

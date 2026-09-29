#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""命令行：用 AKShare 开源数据跑 N 板黑名单。

示例：
    python scripts/run_akshare.py --level 1 --max-stocks 50
    python scripts/run_akshare.py --level 2 --start 2019-01-01 --end 2026-09-24
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from nboard import pipeline  # noqa: E402
from nboard.sources import akshare_source as src  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='N 板黑名单（AKShare 后端）')
    ap.add_argument('--level', type=int, default=1, help='1=首板 2=二板 3=三板')
    ap.add_argument('--start', default='2019-01-01')
    ap.add_argument('--end', default='2026-09-24')
    ap.add_argument('--min-sample', type=int, default=3)
    ap.add_argument('--basis', default='close', choices=['close', 'open', 'both', 'any'])
    ap.add_argument('--at-least', action='store_true', help='至少 N 板（默认恰好第 N 板）')
    ap.add_argument('--max-stocks', type=int, default=None, help='只跑前 N 只（调试用）')
    ap.add_argument('--adjust', default='', help="复权：''=不复权（默认，涨停判定更准）/ qfq / hfq")
    ap.add_argument('--cache-dir', default='./cache')
    ap.add_argument('--out-dir', default='./output')
    ap.add_argument('--sleep', type=float, default=0.2, help='每只间隔秒数，防风控')
    args = ap.parse_args()

    pool = src.get_pool(max_stocks=args.max_stocks)
    print('股票池：%d 只' % len(pool))
    if not pool:
        return
    fetch_start = pipeline.fetch_start(args.start, args.level)
    print('取数区间：%s ~ %s，level=%d' % (fetch_start, args.end, args.level))
    daily = src.get_daily(list(pool), fetch_start, args.end,
                          adjust=args.adjust, cache_dir=args.cache_dir,
                          sleep=args.sleep)
    if daily is None:
        print('未取到数据')
        return
    all_path, black_path = pipeline.run_pipeline(
        pool, daily, args.level, args.start, args.end,
        min_sample=args.min_sample, basis=args.basis,
        exact=not args.at_least, out_dir=args.out_dir)
    print('全量：%s' % all_path)
    print('黑名单：%s' % (black_path or '（无）'))


if __name__ == '__main__':
    main()

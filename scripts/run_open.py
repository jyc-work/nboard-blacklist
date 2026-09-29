#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""命令行：用开源数据跑 N 板黑名单（AKShare / Baostock）。

示例：
    python scripts/run_open.py --source akshare --level 1 --max-stocks 50
    python scripts/run_open.py --source baostock --level 2 --start 2019-01-01 --end 2026-09-24

代理说明（仅 AKShare 受 HTTP 代理影响）：
    默认会**清空系统代理环境变量**再取数（A 股数据在国内，代理常导致 ProxyError）。
    - 需要走系统代理：加 --keep-proxy
    - 指定代理：      --proxy http://127.0.0.1:7890
    Baostock 不走 HTTP 代理，如 AKShare 一直失败可换它。
"""
import argparse
import os
import sys

_PROXY_ENVS = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
               'http_proxy', 'https_proxy', 'all_proxy']


def _configure_proxy(args):
    for k in _PROXY_ENVS:
        os.environ.pop(k, None)
    if args.proxy:
        os.environ['HTTP_PROXY'] = os.environ['HTTPS_PROXY'] = args.proxy
        os.environ['http_proxy'] = os.environ['https_proxy'] = args.proxy
        os.environ.pop('NO_PROXY', None)
        print('使用代理：%s' % args.proxy)
    elif args.keep_proxy:
        os.environ.pop('NO_PROXY', None)
        print('保留系统代理设置')
    else:
        os.environ['NO_PROXY'] = '*'
        print('已绕开系统代理（默认）')


def main():
    ap = argparse.ArgumentParser(description='N 板黑名单（开源数据后端）')
    ap.add_argument('--source', default='akshare', choices=['akshare', 'baostock'])
    ap.add_argument('--level', type=int, default=1, help='1=首板 2=二板 3=三板')
    ap.add_argument('--start', default='2019-01-01')
    ap.add_argument('--end', default='2026-09-24')
    ap.add_argument('--min-sample', type=int, default=3)
    ap.add_argument('--basis', default='close', choices=['close', 'open', 'both', 'any'])
    ap.add_argument('--at-least', action='store_true', help='至少 N 板（默认恰好第 N 板）')
    ap.add_argument('--max-stocks', type=int, default=None, help='只跑前 N 只（调试用）')
    ap.add_argument('--adjust', default='', help="AKShare 复权：''=不复权（默认）/ qfq / hfq")
    ap.add_argument('--cache-dir', default='./cache')
    ap.add_argument('--out-dir', default='./output')
    ap.add_argument('--sleep', type=float, default=0.2, help='AKShare 每只间隔秒数，防风控')
    ap.add_argument('--keep-proxy', action='store_true', help='保留系统代理（默认绕开）')
    ap.add_argument('--proxy', default=None, help='显式代理，如 http://127.0.0.1:7890')
    args = ap.parse_args()

    # 先配置代理，再导入数据源（requests 会读环境变量）
    if args.source == 'akshare':
        _configure_proxy(args)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
    from nboard import pipeline

    if args.source == 'akshare':
        from nboard.sources import akshare_source as src
        pool = src.get_pool(max_stocks=args.max_stocks)
        fetch_start = pipeline.fetch_start(args.start, args.level)
        print('股票池：%d 只，取数 %s ~ %s，level=%d'
              % (len(pool), fetch_start, args.end, args.level))
        daily = src.get_daily(list(pool), fetch_start, args.end,
                              adjust=args.adjust, cache_dir=args.cache_dir, sleep=args.sleep)
    else:
        from nboard.sources import baostock_source as src
        pool = src.get_pool(args.end, max_stocks=args.max_stocks)
        fetch_start = pipeline.fetch_start(args.start, args.level)
        print('股票池：%d 只，取数 %s ~ %s，level=%d'
              % (len(pool), fetch_start, args.end, args.level))
        daily = src.get_daily(list(pool), fetch_start, args.end, cache_dir=args.cache_dir)

    if daily is None:
        print('\n未取到数据。排查建议：')
        print('  1) 默认已尝试绕开代理；仍失败可 --proxy http://127.0.0.1:7890')
        print('  2) 换后端：--source baostock（不走 HTTP 代理）')
        print('  3) 或改用聚宽：研究环境跑 scripts/run_joinquant.py')
        return
    all_path, black_path = pipeline.run_pipeline(
        pool, daily, args.level, args.start, args.end,
        min_sample=args.min_sample, basis=args.basis,
        exact=not args.at_least, out_dir=args.out_dir)
    print('全量：%s' % all_path)
    print('黑名单：%s' % (black_path or '（无）'))


if __name__ == '__main__':
    main()

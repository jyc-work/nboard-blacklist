# -*- coding: utf-8 -*-
"""聚宽研究环境 Notebook 入口：粘贴/运行本文件即可（用聚宽数据，含精确涨停价）。

用法（在 joinquant.com 研究环境新建 Notebook 的一个 cell）：
    %run scripts/run_joinquant.py
或直接把本文件内容粘贴进 cell。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from nboard import pipeline  # noqa: E402
from nboard.sources import joinquant_source as src  # noqa: E402

# ---------------- 参数 ----------------
LEVEL = 1                       # 1=首板 2=二板 3=三板
START = '2019-01-01'
END = '2026-09-24'
MIN_SAMPLE = 3
BASIS = 'close'                 # close / open / both / any
EXACT = True                    # True=恰好第N板；False=至少N板
OUT_DIR = '.'                   # 研究环境当前目录，产物在左侧文件树


def main():
    if not src.available():
        print('未检测到聚宽环境（get_price 不可用）')
        return
    pool = src.get_pool()
    print('股票池：%d 只' % len(pool))
    fetch_start = pipeline.fetch_start(START, LEVEL)
    daily = src.get_daily(list(pool), fetch_start, END)
    if daily is None:
        print('未取到数据')
        return
    industries = src.get_industry_map(list(pool), END)
    all_path, black_path = pipeline.run_pipeline(
        pool, daily, LEVEL, START, END, min_sample=MIN_SAMPLE, basis=BASIS,
        exact=EXACT, industries=industries, out_dir=OUT_DIR)
    print('完成：全量=%s，黑名单=%s' % (all_path, black_path or '（无）'))


if __name__ == '__main__':
    main()

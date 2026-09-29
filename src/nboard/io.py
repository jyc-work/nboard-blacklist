# -*- coding: utf-8 -*-
"""CSV 输出（带 BOM，Excel 直接打开不乱码）。"""
import os


def write_csv(path, df):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return path

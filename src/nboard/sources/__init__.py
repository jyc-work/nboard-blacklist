# -*- coding: utf-8 -*-
"""数据源。统一约定：

每只票 -> 宽表 DataFrame 字典 {'open','high','close','high_limit','paused'}，
索引为交易日 (DatetimeIndex)，列为 6 位代码（聚宽后端保留原始代码）。
"""
from . import akshare_source  # noqa: F401
try:
    from . import baostock_source  # noqa: F401
except Exception:
    pass
try:
    from . import joinquant_source  # noqa: F401
except Exception:  # 非聚宽环境无 get_price 等，忽略
    pass

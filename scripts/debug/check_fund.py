import efinance as ef
import pandas as pd
from datetime import datetime, timedelta

# 获取基金 017811 的历史行情 (最近10个交易日)
fund_code = '017811'
print(f"正在从东方财富抓取基金 {fund_code} 的原始数据...")

# efinance 获取基金净值历史
df = ef.fund.get_quote_history(fund_code)

if df is not None and not df.empty:
    # 转换为 DataFrame 并整理格式
    # 这里的列名通常是 ['日期', '单位净值', '累计净值', '日增长率', ...]
    # 打印所有列名以便确认
    print(f"原始列名：{df.columns.tolist()}")
    # 尝试更通用的匹配方式
    cols = [c for c in df.columns if any(x in c for x in ['日期', '净值', '增长'])]
    print(df[cols].to_markdown(index=False))
else:
    print("未能抓取到数据，请检查代码是否正确。")

import efinance as ef
import pandas as pd

# 你的基金持仓列表
funds = {
    '017811': '东方人工智能主题C',
    '008888': '华夏半导体芯片ETF联接',
    '012414': '招商中证白酒指数',
    '320007': '诺安成长混合',
    '040046': '景顺长城纳指100',
    '005827': '易方达蓝筹精选'
}

print("📊 正在从东方财富抓取最新基金行情...\n")

results = []
for code, name in funds.items():
    try:
        df = ef.fund.get_quote_history(code)
        if df is not None and not df.empty:
            latest = df.iloc[0]  # 最新一条
            prev = df.iloc[1] if len(df) > 1 else None  # 前一天
            
            nav = float(latest['单位净值'])
            prev_nav = float(prev['单位净值']) if prev is not None else nav
            change_pct = (nav - prev_nav) / prev_nav * 100
            
            results.append({
                '代码': code,
                '名称': name,
                '日期': latest['日期'],
                '单位净值': nav,
                '涨跌幅': f"{change_pct:+.2f}%"
            })
    except Exception as e:
        results.append({
            '代码': code,
            '名称': name,
            '日期': '-',
            '单位净值': '-',
            '涨跌幅': f'获取失败: {e}'
        })

# 输出结果
df_result = pd.DataFrame(results)
print(df_result.to_markdown(index=False))

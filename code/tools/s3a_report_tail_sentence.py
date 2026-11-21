"""由 s3a_tail.json 生成网站报告『局限与下一步』的尾部句。用法: python3 -I s3a_report_tail_sentence.py <s3a_tail.json>"""
import sys,json;d=json.load(open(sys.argv[1]));t=d['TS'];s=d['strata'];f=lambda v:f'{v:.2f}'
a=s['10-15']['TS'];b=s['20-inf']['TS']
print(f"- 尾部形状另做了超阈值检验（广义帕累托分布，取 90% 分位以上）：雷暴阵风比的形状参数 ξ = {f(t['xi'])}，95% 区间 [{f(t['xi_ci'][0])}, {f(t['xi_ci'][1])}]（ξ>0 表示重尾），但阈值改取 95% 分位时降到 {f(t['xi_by_threshold']['0.95'])}，结果对阈值敏感。按平均风分层后，重尾主要来自平均风较低的 10–15 节层（ξ = {f(a['xi'])}，[{f(a['xi_ci'][0])}, {f(a['xi_ci'][1])}]）；平均风 ≥20 节层 ξ = {f(b['xi'])}，[{f(b['xi_ci'][0])}, {f(b['xi_ci'][1])}]，为有界尾。这一分层规律是看数据后发现的，正在另一批未用过的雷暴事件上检验。")

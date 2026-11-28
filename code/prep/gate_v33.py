#!/usr/bin/env python3
"""L22.6 T03 v3.3 闸门与校准计算存档（准备 5，Lead 11-27）。输入 aggregate_v33.py 的 csv。
去重（dup_of 非空的行丢弃）；样本 sd 用 n−1；全部由未舍入值计算。
输出：REF 带 I(rho_in)；E2 闸（C_I vs C_I⁻，|Δmean| ≥ 3·合并 sd，合并 sd=√((s1²+s2²)/2)，同阶段 0 实验卡⑤）；各组风向最大值。"""
import csv,sys,statistics as st,math
R=[r for r in csv.DictReader(open(sys.argv[1])) if not r['dup_of']]
G=lambda g,c:[float(r[c]) for r in R if r['group']==g and r[c] not in ('','None')]
m,s=st.mean(G('REF','max_rho_in')),st.stdev(G('REF','max_rho_in'))
print(f"REF n={len(G('REF','max_rho_in'))} rho_in {m:.6f}±{s:.6f}  I=[{max(0,m-3*s):.6f}, {m+3*s:.6f}]")
a,b=G('P_CI','e_Ly_v33'),G('P_CIminus','e_Ly_v33'); sp=math.sqrt((st.stdev(a)**2+st.stdev(b)**2)/2)
print(f"E2 gate (censor<3 applied): n={len(a)},{len(b)} |{st.mean(a):.6f}-{st.mean(b):.6f}|={abs(st.mean(a)-st.mean(b)):.6f} vs 3sd={3*sp:.6f} -> {'keep' if abs(st.mean(a)-st.mean(b))>=3*sp else 'downgrade'}")
for g in sorted({r['group'] for r in R}):
    d=G(g,'max_dir_err_deg')
    print(f"{g}: n={len(d)} max_dir_err_deg max {max(d):.4f} mean {st.mean(d):.4f}" if d else f"{g}: no direction")

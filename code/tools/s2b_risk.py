"""S2a-next 风险框架（方案增补 11-27）。失效态占比 q → 期望劣化增量 ΔE=q·(𝔉_fail−𝔉_P)，与主动律可得收益 0.0088 比较。
用法: python3 -I s2b_risk.py <s2a_v2.json> <out.json>"""
import sys,json,math
d=json.load(open(sys.argv[1]));Fo=d['SA']['F_c0'];Fl=d['SA']['F_locked'];Fp=d['SA']['F_at_C']
gain=max(x['R_x'] for x in d['LQG'] if 'R_x' in x)
src={
 'zero_failure_upper_0.0059_tau0.1y':0.0059*0.1/(1+0.0059*0.1),
 'zero_failure_upper_0.0059_tau2y':0.0059*2/(1+0.0059*2),
 'snubber_inspection_prevalence_1.2pct':0.012,
 'snubber_functional_test_prevalence_5.9pct':0.059,
}
rows={k:dict(q=q,dE_open=q*(Fo-Fp),dE_locked=q*(Fl-Fp)) for k,q in src.items()}
for k,r in rows.items():print(k,{a:round(b,5) for a,b in r.items()})
out=dict(F_open=Fo,F_locked=Fl,F_passive=Fp,active_gain_max=gain,rows=rows,
 Pfail25_upper=1-math.exp(-0.0059*25),q_break_open=gain/(Fo-Fp),q_break_locked=gain/(Fl-Fp))
print('gain',gain,'q_break open/locked',out['q_break_open'],out['q_break_locked'],'P(≥1 failure in 25y | λ=0.0059)',out['Pfail25_upper'])
json.dump(out,open(sys.argv[2],'w'),indent=1)

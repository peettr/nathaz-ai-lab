#!/usr/bin/env python3
"""Analyze try12 measured CSV; fail closed. No solver execution."""
import csv,json,math,sys
from pathlib import Path
R=Path(sys.argv[1]); W=R/'try12_noshear_wall.csv'; N=R/'try12_native_wall.csv'; P=R/'try12_noshear_pulse.csv'
def rows(p):
    with p.open(newline='') as f:a=list(csv.DictReader(f))
    assert a and all(all(math.isfinite(float(x)) for x in r.values()) for r in a),(p,'nonfinite or empty')
    return a
w=rows(W);n=rows(N);p=rows(P)
assert len(w)==len(n)==2001 and [int(r['step']) for r in w]==list(range(2001)) and [int(r['step']) for r in n]==list(range(2001))
f=lambda r,k:float(r[k]); m0=f(w[0],'rho_mass'); px0=f(w[0],'px'); jump=f(w[1],'rho_mass')-m0
expected=(24*24*2)*1.5*(0.035**2)/18
# Pair indices (2,3), (4,5), ... (1998,1999); compare every pair mean to the first.
pairs=[(f(w[t],'rho_mass')+f(w[t+1],'rho_mass'))/2 for t in range(2,2000,2)]
drift=max(abs(x-pairs[0]) for x in pairs)
px_rel=max(abs(f(x,'px')-px0)/abs(px0) for x in w)
native_jump=f(n[1],'rho_mass')-f(n[0],'rho_mass')
assert len(p)==4 and {(int(r['parity']),int(r['variant'])) for r in p}=={(0,0),(0,1),(1,0),(1,1)}
pulses=[]
for parity in (0,1):
    base=next(r for r in p if int(r['parity'])==parity and int(r['variant'])==0)
    perturb=next(r for r in p if int(r['parity'])==parity and int(r['variant'])==1)
    dose=f(perturb,'source_slot_after_injection')-f(perturb,'source_slot_before')
    pre=f(perturb,'target_after_injection')-f(base,'target_after_injection')
    pre0=f(perturb,'target_before')-f(base,'target_before')
    after=f(perturb,'target_after_step')-f(base,'target_after_step')
    fluid=f(perturb,'fluid_rho_after_step')-f(base,'fluid_rho_after_step')
    immediate=f(perturb,'fluid_rho_after_injection')-f(base,'fluid_rho_after_injection')
    pulses.append({'parity':parity,'dose':dose,'target_before':pre0,'target_post_injection':pre,'target_plus1':after,'fluid_delta_post_injection':immediate,'fluid_delta_plus1':fluid,'pass':all((abs(pre0)<1e-6,abs(pre)<1e-6,abs(after-dose)<=1e-6,abs(fluid-dose)<=1e-6,abs(immediate)<1e-6))})
report={'rows':len(w),'rho0':m0,'jump_measured':jump,'jump_predicted':expected,'jump_rel_error':abs(jump-expected)/expected,'jump_pass':abs(jump-expected)<=0.01*expected,'two_step_pair_count':len(pairs),'two_step_max_abs_drift':drift,'two_step_limit':1e-6*m0,'two_step_pass':drift<=1e-6*m0,'px0':px0,'max_px_rel_0to2000':px_rel,'px_pass':px_rel<=1e-6,'native_first_jump':native_jump,'native_pass':abs(native_jump)<=1e-6*m0,'pulses':pulses}
report['all_pass']=all(report[k] for k in ('jump_pass','two_step_pass','px_pass','native_pass')) and all(x['pass'] for x in pulses)
print(json.dumps(report,indent=2,ensure_ascii=False))

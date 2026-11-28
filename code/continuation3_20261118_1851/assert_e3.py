#!/usr/bin/env python3
"""Fail-closed E3 gate on native per-column records, not synthetic physics."""
import csv, math, pathlib, sys, json
p=pathlib.Path(sys.argv[1]);rows=list(csv.DictReader(p.open()))
if not rows: raise ValueError('no E3 records')
fields=('tau_f_x_lattice','tau_f_y_lattice','tau_f_abs_lattice','applied_force_x_lattice','applied_force_y_lattice','area_lattice','match_speed_lattice','tau_w_theory_lattice','relative_error')
for r in rows:
    for f in fields:
        if not math.isfinite(float(r[f])):raise ValueError(f'nonfinite {f}')
    if float(r['area_lattice'])<=0:raise ValueError('nonpositive area')
    if abs(float(r['tau_f_abs_lattice'])-math.hypot(float(r['tau_f_x_lattice']),float(r['tau_f_y_lattice'])))>1e-8:raise ValueError('tau components inconsistent')
    err=math.hypot(float(r['applied_force_x_lattice'])+float(r['tau_f_x_lattice'])*float(r['area_lattice']),float(r['applied_force_y_lattice'])+float(r['tau_f_y_lattice'])*float(r['area_lattice']))
    if err>1e-6*max(float(r['tau_f_abs_lattice']),1e-20):raise ValueError('force inconsistent')
nonzero=sum(abs(float(r['tau_f_abs_lattice']))>0 for r in rows)
ratio=nonzero/len(rows)
tau=sum(float(r['tau_f_abs_lattice']) for r in rows)/len(rows)
theory=sum(float(r['tau_w_theory_lattice']) for r in rows)/len(rows)
relative=max(float(r['relative_error']) for r in rows)
verdict={'samples':len(rows),'nonzero_fraction':ratio,'tau_f_mean':tau,'tau_w_theory_mean':theory,'tau_ratio':tau/theory if theory>0 else None,'max_force_relative_error':relative,'nonzero_pass':ratio>=.99,'theory_pass':theory>0 and abs(tau/theory-1)<=.2,'force_pass':relative<=1e-6}
verdict['pass']=all(verdict[k] for k in ('nonzero_pass','theory_pass','force_pass'))
print(json.dumps(verdict,sort_keys=True),flush=True)
if not verdict['pass']:sys.exit(2)

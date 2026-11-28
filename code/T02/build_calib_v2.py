#!/usr/bin/env python3
"""Merge verified small SL C output with existing A/B/Q/MC rows; no solve here."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent
src=root/'calib_T02.csv'; pred=root/'sl_C_results.json'; dest=root/'calib_T02_v2.csv'
if dest.exists():raise FileExistsError(dest)
with src.open(newline='') as f: rows=list(csv.DictReader(f))
assert len(rows)==16 and len({(x['case'],x['method']) for x in rows})==16
values=json.loads(pred.read_text())['cases']
assert set(values)=={'small','medium','large','X'}
new=[]
for case in ('small','medium','large','X'):
    m=next(r for r in rows if r['case']==case and r['method']=='MC')
    c=values[case]; fixed=c['fixed'];sq=fixed['sigma_q'];ss=fixed['sigma_stroke']
    out={key:'' for key in rows[0]}
    out.update(case=case,method='C',sigma_q_m=sq,sigma_stroke_m=ss,
               nu_opt=c['nu_opt'],nu_opt_basis='SL_C_optimized',
               rel_error_sigma_q_vs_MC=sq/float(m['sigma_q_m'])-1,
               rel_error_sigma_stroke_vs_MC=ss/float(m['sigma_stroke_m'])-1)
    new.append(out)
rows.extend(new)
assert len(rows)==20
with dest.open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({'path':str(dest),'rows':len(rows),'C':{x['case']:{'sigma_q':x['sigma_q_m'],'nu_opt':x['nu_opt']} for x in new}}))

#!/usr/bin/env python3
"""Small-file aggregation only; scientific simulation remains on CRC."""
import csv, json, math
from pathlib import Path
root=Path(__file__).resolve().parent
sl=json.loads((root/'sl_results.json').read_text())
raw=root/'mc_raw'
base={'small':'small_01','medium':'medium_02','large':'large_03','X':'X_04'}
mc={k:json.loads((raw/(v+'.json')).read_text()) for k,v in base.items()}
scan=[json.loads((raw/f'large_{i:02}.json').read_text()) for i in (3,5,6,7,8)]
assert len(scan)==5 and all(x['case']=='large' for x in scan)
nu_best=min(scan,key=lambda x:x['sigma_q'])['nu']
rows=[]
for case in ('small','medium','large','X'):
    m=mc[case]
    half=(m['ci95_sigma_q'][1]-m['ci95_sigma_q'][0])/(2*m['sigma_q'])
    assert m['n_traj']>=200 and m['T_s']>=1800 and half<=.01, (case,half)
    for method in ('MC','A','B','Q'):
        d=(m if method=='MC' else sl['cases'][case]['methods'][method]['fixed'])
        sq=d['sigma_q']; ss=d['sigma_stroke']
        row={'case':case,'method':method,'sigma_q_m':sq,'sigma_stroke_m':ss,
             'nu_opt':nu_best if method=='MC' and case=='large' else
             (m['nu'] if method=='MC' else sl['cases'][case]['methods'][method]['nu_opt']),
             'nu_opt_basis':('5_point_MC_scan' if method=='MC' and case=='large' else
                              'not_scanned_fixed_linear_point' if method=='MC' else 'SL_optimized'),
             'rel_error_sigma_q_vs_MC':sq/m['sigma_q']-1,
             'rel_error_sigma_stroke_vs_MC':ss/m['sigma_stroke']-1,
             'ci95_sigma_q_lo_m':m['ci95_sigma_q'][0] if method=='MC' else '',
             'ci95_sigma_q_hi_m':m['ci95_sigma_q'][1] if method=='MC' else '',
             'ci95_sigma_stroke_lo_m':m['ci95_sigma_stroke'][0] if method=='MC' else '',
             'ci95_sigma_stroke_hi_m':m['ci95_sigma_stroke'][1] if method=='MC' else '',
             'MC_sigma_q_CI_relative_halfwidth':half if method=='MC' else ''}
        rows.append(row)
assert len(rows)==16
out=root/'calib_T02.csv'
if out.exists():raise FileExistsError(out)
with out.open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({'rows':len(rows),'cases':list(base),'large_MC_scan':[(x['nu'],x['sigma_q']) for x in sorted(scan,key=lambda x:x['nu'])], 'CI_relative_halfwidth':{k:(m['ci95_sigma_q'][1]-m['ci95_sigma_q'][0])/(2*m['sigma_q']) for k,m in mc.items()},'path':str(out)}))

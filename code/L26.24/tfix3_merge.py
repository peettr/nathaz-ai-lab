"""Merge Tfix3's separately executed B1/B2/L1 rows and recalculate Ta quartiles."""
import csv,json
from pathlib import Path
from statistics import median
import numpy as np
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix3')
OUT=ROOT/'out'
NAMES={f'PresCorr-{i}-2' for i in range(220182,220187)}
FIELDS=['system','method','target','rep','initial_residual','target_residual','setup_seconds','inference_seconds','cg_seconds','total_seconds','iterations','achieved_residual','status','source']
parts=[]
for method in ('B1','B2','L1'):
    rows=list(csv.DictReader((OUT/f'{method.lower()}.csv').open()))
    assert len(rows)==25 and {r['system'] for r in rows}==NAMES
    assert len({(r['system'],r['rep']) for r in rows})==25
    assert all(r['method']==method and r['target']=='Ta' and r['status'] in ('converged','initial_meets_target') and float(r['achieved_residual'])<=float(r['target_residual']) for r in rows)
    parts+=rows
assert len(parts)==75
with (OUT/'ta_corr2_fix.csv').open('x',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(parts)
summary={'source':'D1b later exported 20; B1/B2/L1 original CSV with five corrected corr2 systems','quantile':'numpy linear; per-system five repeats median then cross-system Q1/Q3','methods':{},'corrected_systems':sorted(NAMES),'correction_rows':75,'Ta_target':'corr1-3=max(1e-6, .05*initial); corr4=1e-6','Tb':'unchanged'}
for method in ('B1','B2','L1'):
    path=ROOT/('l1_timing_original.csv' if method=='L1' else 'baseline_timing_original.csv')
    original=[r for r in csv.DictReader(path.open()) if r['segment']=='later' and r['target']=='Ta' and (method=='L1' or r['baseline']==method)]
    assert len(original)==100,(method,len(original))
    rows=[r for r in original if r['system'] not in NAMES]+[r for r in parts if r['method']==method]
    assert len(rows)==100 and len({(r['system'],r.get('repetition',r.get('rep'))) for r in rows})==100
    assert all(r['status'] in ('converged','initial_meets_target') and float(r['achieved_residual'])<=float(r['target_residual']) for r in rows)
    groups={}
    for r in rows:groups.setdefault(r['system'],[]).append(float(r['total_seconds']))
    assert len(groups)==20 and all(len(v)==5 for v in groups.values())
    vals=[median(v) for v in groups.values()]
    q1,q3=map(float,np.quantile(vals,[.25,.75]))
    summary['methods'][method]={'systems':20,'repeats_per_system':5,'median_seconds':float(median(vals)),'q1_seconds':q1,'q3_seconds':q3,'iqr_seconds':q3-q1,'converged_rows':len(rows),'per_system_medians_seconds':dict(sorted((k,float(median(v))) for k,v in groups.items()))}
summary['thresholds_seconds']={'Ta_L1_le_0p8_B0_48':.0241,'Ta_L1_le_0p8_B1':5.44,'Tb_L1_ge_0p8_B0_48':.222}
l=summary['methods']['L1']['median_seconds'];summary['L1_Ta_le_B0_threshold']=l<=.0241;summary['L1_Ta_le_B1_threshold']=l<=5.44
(OUT/'ta_fixed_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
print('TFIX3_MERGE_COMPLETE',len(parts),json.dumps({k:{x:v for x,v in o.items() if x!='per_system_medians_seconds'} for k,o in summary['methods'].items()}),flush=True)

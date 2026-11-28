"""Merge immutable five-system Ta corrections and compute per-system median / Q1-Q3."""
import csv, json, sys
from pathlib import Path
from statistics import median
import numpy as np
BASE=Path('./26_Quick_Trials/06_Logs/L26.24')
NAMES={f'PresCorr-{i}-2' for i in range(220182,220187)}
SRC={'B1':BASE/'baseline_timing_B1_B2_partial.csv','B2':BASE/'baseline_timing_B1_B2_partial.csv','L1':BASE/'l1_timing.csv'}

def main(corrected):
    fresh=list(csv.DictReader(open(corrected,newline='')))
    assert len(fresh)==75 and {(r['system'],r['method'],r['rep']) for r in fresh}.__len__()==75
    assert {r['system'] for r in fresh}==NAMES
    out={'source':'D1b later exported 20; original B1/B2/L1 CSV with five corrected corr2 systems', 'quantile':'numpy linear interpolation; five repeats median per system then Q1/Q3 of 20','methods':{},'corrected_systems':sorted(NAMES),'correction_rows':75,'Ta_target':'corr1-3=max(1e-6, .05*initial); corr4=1e-6','Tb':'unchanged'}
    for method in ('B1','B2','L1'):
        original=[r for r in csv.DictReader(open(SRC[method],newline='')) if r['segment']=='later' and r['target']=='Ta' and (method=='L1' or r['baseline']==method)]
        assert len(original)==100,(method,len(original))
        retained=[r for r in original if r['system'] not in NAMES]
        patched=[r for r in fresh if r['method']==method]
        rows=retained+patched
        assert len(rows)==100 and len({(r['system'],r.get('repetition',r.get('rep'))) for r in rows})==100
        assert all(r['status'] in ('converged','initial_meets_target') and float(r['achieved_residual'])<=float(r['target_residual']) for r in rows)
        groups={}
        for r in rows:groups.setdefault(r['system'],[]).append(float(r['total_seconds']))
        assert len(groups)==20 and all(len(v)==5 for v in groups.values())
        vals=[median(v) for v in groups.values()]
        q1,q3=map(float,np.quantile(vals,[.25,.75]))
        out['methods'][method]={'systems':20,'repeats_per_system':5,'median_seconds':float(median(vals)),'q1_seconds':q1,'q3_seconds':q3,'iqr_seconds':q3-q1,'converged_rows':len(rows),'per_system_medians_seconds':dict(sorted((k,float(median(v))) for k,v in groups.items()))}
    out['thresholds_seconds']={'Ta_L1_le_0p8_B0_48':.0241,'Ta_L1_le_0p8_B1':5.44,'Tb_L1_ge_0p8_B0_48':.222}
    l=out['methods']['L1']['median_seconds'];out['L1_Ta_le_B0_threshold']=l<=.0241;out['L1_Ta_le_B1_threshold']=l<=5.44
    dest=BASE/'ta_fixed_summary.json'
    assert not dest.exists()
    dest.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({k:{x:v for x,v in o.items() if x!='per_system_medians_seconds'} for k,o in out['methods'].items()},ensure_ascii=False))
if __name__=='__main__':main(sys.argv[1])

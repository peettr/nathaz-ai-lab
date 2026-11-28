#!/usr/bin/env python3
"""Independent audit of C1 returned logs; frozen criteria in EXPERIMENT_CARD_C1.md."""
import gzip, json, re, statistics
from pathlib import Path
p=Path(__file__).parent/'returned'/'logs'
num=r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
fields=('Ux','Uy','Uz','p','nuTilda')
results={}
for grade in ('coarse','medium'):
    stem=f'{grade}_base_0002'
    txt=gzip.open(p/f'{stem}_rank0.gz','rt').read()
    res={f:[] for f in fields}
    for f,v in re.findall(r'Solving for\s+([A-Za-z][A-Za-z0-9]*),\s+Initial residual\s*=\s*'+num,txt):
        if f in res:res[f].append(float(v))
    raw_p=len(res['p'])
    assert raw_p==3*len(res['Ux']) and len(res['Ux'])==5000,(grade,raw_p,len(res['Ux']))
    res['p']=res['p'][0::3]
    trace=[float(v) for v in re.findall(r'^\s*roofCp:\s*'+num,txt,re.M)]
    assert len(trace)==5000,(grade,len(trace))
    ratios={f:res[f][-1]/res[f][0] for f in fields}
    cp_change=abs(trace[-1]-trace[-500])/abs(trace[-500])
    gate=all(v<=1e-4 for v in ratios.values()) and cp_change<0.005
    reported=json.load(gzip.open(p/f'{stem}_primal_gate.gz','rt'))
    assert gate==reported['primal_gate'] and all(abs(v/reported['residual_ratios'][f]-1)<1e-8 for f,v in ratios.items())
    assert abs(cp_change-reported['cp_last500_change'])<1e-10
    checks=(p/f'{grade}_checkMesh.log').read_text()
    times=[float(x) for x in re.findall(r'ExecutionTime\s*=\s*'+num,txt)]
    results[grade]={
        'cells':reported['cells'],'mesh_ok':'Mesh OK' in checks,'steps':len(trace),
        'p_raw_corrections':raw_p,'residual_ratio_first_corrector':ratios,
        'p_last2000_block500_mean':[statistics.mean(res['p'][i:i+500]) for i in range(3000,5000,500)],
        'cp_last':trace[-1],'cp_4501':trace[-500],
        'cp_last500_mean':statistics.mean(trace[-500:]),
        'cp_last500_change':cp_change,'gate':gate,
        'execution_times_tail':times[-3:],
        'roof_yplus':(p/f'{grade}_base_yplus.txt').read_text().strip()
    }
print(json.dumps(results,indent=2,ensure_ascii=False))

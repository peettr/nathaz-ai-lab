#!/usr/bin/env python3
"""Reconcile the interrupted seven-variant preflight without rewriting evidence."""
import hashlib,json,pathlib
r=pathlib.Path(__file__).resolve().parent
old=pathlib.Path('06_Logs/R21.4a_T15_second_layer_WM/continuation8b_20261119_0026')
if not old.exists(): old=r.parents[1]/'R21.4a_T15_second_layer_WM/continuation8b_20261119_0026'
root=r/'seven_variants_A6_v2'
variants=('periodic_bounce','periodic_t4','periodic_t15_k2','periodic_t15_k3','legacy_off','legacy_on','legacy_k3')
result={}
for name in variants:
    d=root/name
    logs={key:next((p.read_text() for p in (d/(key+'.syntax.log'),d/(key+'.syntax.recovery.log')) if p.exists()),'') for key in ('kernel.cpp','lbm.cpp','setup.cpp')}
    generated=d/'generated.cl'
    record={'syntax':{k:'exit=0' in v for k,v in logs.items()},'generated':generated.is_file()}
    if generated.is_file():
        b=generated.read_bytes();record['sha256']=hashlib.sha256(b).hexdigest()
        if name.startswith('legacy_'):
            ref=old/(name.removeprefix('legacy_')+'_new_kernel_container.cl')
            record['reference']=str(ref);record['reference_sha256']=hashlib.sha256(ref.read_bytes()).hexdigest()
            record['byte_equal']=b==ref.read_bytes()
    result[name]=record
print(json.dumps(result,ensure_ascii=False,indent=2))
assert all(len(v['syntax'])==3 and all(v['syntax'].values()) and v['generated'] and (not k.startswith('legacy_') or v['byte_equal']) for k,v in result.items())
(r/'PREFLIGHT_RECONCILED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

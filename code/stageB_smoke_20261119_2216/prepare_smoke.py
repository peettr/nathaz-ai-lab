#!/usr/bin/env python3
"""Freeze a fresh T17 smoke package; predecessor is read-only."""
import pathlib, shutil, json, hashlib, difflib
R=pathlib.Path(__file__).resolve().parent
OLD=R.parent/'stageB_native_v2_20261119_2140'
for n in ('worker_native.py','native_analysis.py','stub_native.py','dry_native.py','controller_native.py','remote_B.py','assert_T17.py','test_assert_T17.py','machine.py','seal_stage.py','SESSION_PLAN.json','DATA_CONTRACT.md','t17_b_native.inc'):
 shutil.copy2(OLD/n,R/n)
shutil.copytree(OLD/'pack_stage',R/'pack_stage')
def replace(n,a,b):
 p=R/n;s=p.read_text();assert s.count(a)==1,(n,a,s.count(a));p.write_text(s.replace(a,b))
replace('t17_b_native.inc','(mode=="smoke")?250ul','(mode=="smoke")?200ul')
replace('t17_b_native.inc','(mode=="smoke")?1000ul:5ul*Tsteps','(mode=="smoke")?2000ul:5ul*Tsteps')
replace('t17_b_native.inc','(mode=="smoke")?1000ul:4ul*half','(mode=="smoke")?800ul:4ul*half')
replace('t17_b_native.inc','(mode=="smoke")?100ul:200ul','(mode=="smoke")?50ul:200ul')
replace('t17_b_native.inc','(mode=="smoke")?50ul:100ul','(mode=="smoke")?50ul:100ul') if False else None
# Same smoke producer in every staged variant; physical kernel/lbm/defines untouched.
for group in ('periodic_bounce','periodic_t4','periodic_t15_k2'):
 shutil.copy2(R/'t17_b_native.inc',R/'pack_stage'/group/'src/t17_b_native.inc')
replace('worker_native.py',"half=round(budget['steps_per_T']/2)","half=200 if mode=='smoke' else round(budget['steps_per_T']/2)")
replace('worker_native.py',"fixture_decision(d,a,end,half) if budget.get('fixture') else decide(d,a,end,half,mode=='smoke')","decide(d,a,end,half,mode=='smoke')")
replace('worker_native.py',"2000 if mode=='smoke' else 10*budget['steps_per_T']","2800 if mode=='smoke' else 10*budget['steps_per_T']")
replace('worker_native.py',"result=summarize(d)\n    checks=seed_metrics(result)","result=summarize(d)\n    checks=seed_metrics(result)\n    cloned={'schema':'T17-B-v1','cases':{g:{s:result for s in SEEDS} for g in GROUPS}}\n    pipeline=evaluate(cloned)\n    def finite_tree(obj):\n     if isinstance(obj,float):return __import__('math').isfinite(obj)\n     if isinstance(obj,dict):return all(finite_tree(v) for v in obj.values())\n     if isinstance(obj,list):return all(finite_tree(v) for v in obj)\n     return True\n    if not finite_tree(result) or not finite_tree(pipeline):raise RuntimeError('nonfinite contract/assert output')")
replace('worker_native.py',"'assert_T17_seed_metrics':checks,'science_verdict'","'assert_T17_seed_metrics':checks,'assert_T17_cloned_pipeline':pipeline,'science_verdict'")
replace('stub_native.py',"f.write('0,1000,pending,250,0.01282051,78,32768,100,smoke\\n')","f.write('0,2000,pending,200,0.01282051,78,32768,50,smoke\\n')")
replace('stub_native.py',"range(0,2001,50)","range(0,2801,50)")
replace('stub_native.py',"(p/'v0_0.ready').write_text('1000\\n')","(p/'v0_0.ready').write_text('2000\\n')")
replace('stub_native.py',"(p/'statistics_start.txt').write_text('1000\\n')","(p/'statistics_start.txt').write_text('2000\\n')")
replace('stub_native.py',"range(1100,2001,100)","range(2050,2801,50)")
replace('stub_native.py',"range(10):","range(16):")
replace('stub_native.py',"(p/'producer.done').write_text('2000\\n')","(p/'producer.done').write_text('2800\\n')")
replace('controller_native.py',"2000/plan['steps_per_second']['t15']","2800/plan['steps_per_second']['t15']")
# smoke must exercise smoke analysis path rather than skipping V0 decision.
replace('dry_native.py',"assert json.loads((C/'t17b/out/smoke_pipeline.json').read_text())['finite']","smoke=json.loads((C/'t17b/out/smoke_pipeline.json').read_text());assert smoke['finite'] and smoke['assert_T17_cloned_pipeline']['schema']=='T17-B-result-v1'\nassert (C/'t17b/out/t15_s1/v0_0.decision').read_text().strip()=='pass'\nassert smoke['contract']['native_provenance']['frames']==16")
for n in ('t17_b_native.inc','worker_native.py','native_analysis.py','stub_native.py','controller_native.py','dry_native.py'):
 a=(OLD/n).read_text().splitlines(True);b=(R/n).read_text().splitlines(True)
 (R/(n+'.diff')).write_text(''.join(difflib.unified_diff(a,b,fromfile='old/'+n,tofile='smoke/'+n)))
(R/'SOURCE_SHA256.json').write_text(json.dumps({str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((R/'pack_stage').rglob('*')) if p.is_file() and p.name in ('kernel.cpp','lbm.cpp','defines.hpp','setup.cpp','t17_b_native.inc')},indent=2)+'\n')
print('PREPARED',R)

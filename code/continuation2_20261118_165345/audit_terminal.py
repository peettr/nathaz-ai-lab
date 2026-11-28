#!/usr/bin/env python3
"""Read-only terminal evidence audit; writes a separate v2 verdict, preserves v1."""
import csv, hashlib, json, math
from pathlib import Path
R=Path(__file__).resolve().parent
E=R/'session_luw-t15-a100-adacd84b/evidence'
O=R/'postprocess_v2'
O.mkdir(exist_ok=False)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check(p):
 assert p.is_file() and sha(p)==(p.parent/(p.name+'.sha256')).read_text().strip(),str(p)
 return sha(p)
cases=['E3_native','WM_s107','WM_s108','WM_s109','K3_s107']
verified={}
for case in cases:
 h=json.loads((E/(case+'_handoff.json')).read_text())['sha256']
 for name,digest in h.items():assert check(E/name)==digest,(case,name)
 x=json.loads((E/(case+'_exit.json')).read_text())
 assert x['solver_exit']==0,(case,x)
 verified[case]={'file_count':len(h),'handoff_sha256':sha(E/(case+'_handoff.json')),'solver_exit':x['solver_exit']}
assert json.loads((E/'run.done').read_text())=={'verified_cases':cases,'mode':'production'}
check(E/'run.done')
compile_check={}
for n in ['off','on','e3','k3']:
 text=(E/(n+'_gpu_compile.log')).read_text(errors='replace')
 check(E/(n+'_gpu_compile.log'))
 assert 'OpenCL C code successfully compiled.' in text and 'T15 COMPILE_ONLY PASS '+n in text,n
 compile_check[n]={'pass':True,'sha256':sha(E/(n+'_gpu_compile.log'))}
with (E/'E3_native_native_e3.csv').open() as f: rows=list(csv.DictReader(f))
assert len(rows)>0
err=[float(r['relative_error']) for r in rows]; tau=[float(r['tau_f_x_lattice']) for r in rows]; force=[float(r['applied_force_x_lattice']) for r in rows]
assert all(math.isfinite(x) for x in err+tau+force)
e3={'samples':len(rows),'max_relative_error_reported':max(err),'nonzero_tau_samples':sum(x!=0 for x in tau),'nonzero_applied_force_samples':sum(x!=0 for x in force),'pass_nontrivial_force_gate':max(err)<=1e-6 and any(x!=0 for x in tau) and any(x!=0 for x in force),'reason':'all-zero tau and force make relative-error equality vacuous; no applied-force validation'}
wall={}
for case in cases[1:]:
 with (E/(case+'_wall_tau_actual.csv')).open() as f: rs=list(csv.DictReader(f))
 cols=['tau_abs_over_rho_lattice','fx_over_rho_lattice','fy_over_rho_lattice','ustar_mps']
 counts={k:sum(float(row[k])!=0 for row in rs) for k in cols}
 assert all(math.isfinite(float(row[k])) for row in rs for k in cols)
 wall[case]={'rows':len(rs),'nonzero_counts':counts,'sha256':check(E/(case+'_wall_tau_actual.csv'))}
v1=json.loads((R/'postprocess_v1/T15_verdict.json').read_text())
report={'status':'ENGINEERING_GATE_E3_UNVERIFIED_ZERO_FORCE','source_sha256':sha(R/'t15_stage.tar.gz'),'e1':'PASS_CPU_SOURCE_LINKED (CPU audit only)','e2':'PASS from previous run; not repeated','e4':'PASS true worker + solver stub and four injected timeouts (orchestration only)','gpu_compile':compile_check,'e3':e3,'verified_cases':verified,'wall_columns':wall,'G1':{'evaluated':False,'descriptive':v1['G1'],'reason':'E3 prerequisite did not demonstrate nonzero wall stress'},'G2':{'evaluated':False,'descriptive':v1['G2'],'reason':'E3 prerequisite did not demonstrate nonzero wall stress'},'G3':{'evaluated':False,'descriptive':v1['G3'],'reason':'all sampled ustar are zero; not a valid active-model test'},'k3_report_only':v1['k3_s107_report_only'],'verdict':'工程闸门 E3 未证实（零应力/零施力），空场科学闸门不判；原 postprocess_v1 的“中间”不能用于验收。','root':str(R)}
p=O/'T15_verdict.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n');(O/'T15_verdict.json.sha256').write_text(sha(p)+'\n')
print(json.dumps({'E3':e3,'wall':wall,'compile':compile_check,'verdict':report['verdict'],'output':str(p)},ensure_ascii=False))

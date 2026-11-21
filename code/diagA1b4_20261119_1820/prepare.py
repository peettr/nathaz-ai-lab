#!/usr/bin/env python3
import pathlib,shutil,difflib,hashlib,json,tarfile,subprocess
R=pathlib.Path(__file__).resolve().parent; B=R.parent
A=B/'stageA13_20261119_1421/work/pack_stage/periodic_t4'; OLD=B/'diagA1b3_sealed_20261119_151419'
S=R/'stage';assert not S.exists();shutil.copytree(A,S)
p=S/'src/setup.cpp';a=p.read_text();s=a
needle='    ledger<<"step,mass_fluid_lattice,px_fluid_lattice,ground_drag_snapshot,eligible_native_columns,ground_drag_integral_10,ground_drag_integral_50\\n";'
assert s.count(needle)==1
s=s.replace(needle,needle+'\n    const char* layer_path=std::getenv("T17_LAYER_CSV");\n    if(a1b_diag && (!layer_path || !*layer_path)) print_error("T17 layer path required");\n    std::ofstream layer;\n    if(a1b_diag) { layer.open(layer_path,std::ios::out|std::ios::trunc); if(!layer) print_error("T17 cannot open layer CSV"); layer<<"step,z,px_lattice,mass_lattice\\n"; }',1)
needle='        double mass=0.0,px=0.0; ulong eligible=0ul;';assert s.count(needle)==1;s=s.replace(needle,needle+'\n        double layer_px[66]={0.0},layer_mass[66]={0.0};',1)
needle='                    px+=(double)lbm.rho[n]*(double)lbm.u.x[n];';assert s.count(needle)==1;s=s.replace(needle,needle+'\n                    if(a1b_diag) {layer_px[z]+=(double)lbm.rho[n]*(double)lbm.u.x[n];layer_mass[z]+=(double)lbm.rho[n];}',1)
needle='        ledger.flush();';assert s.count(needle)==1;s=s.replace(needle,needle+'\n        if(a1b_diag) {for(uint z=1u;z<=64u;++z) layer<<step<<","<<z<<","<<std::setprecision(17)<<layer_px[z]<<","<<layer_mass[z]<<"\\n";layer.flush();}',1)
# A13 already calls update_fields before sample for diagnosis. Keep that order.
assert 'if(a1b_diag) lbm.update_fields();' in s and 'top_initialize_incoming' in (S/'src/kernel.cpp').read_text()
p.write_text(s)
(R/'SOURCE_vs_A13.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True),s.splitlines(True),fromfile='A13/setup.cpp',tofile='D1/setup.cpp')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=['kernel.cpp','lbm.cpp','setup.cpp','defines.hpp'];source={n:sha(S/'src'/n) for n in files};base={n:sha(A/'src'/n) for n in files};assert all(source[n]==base[n] for n in files if n!='setup.cpp')
(R/'SOURCE_PROVENANCE.json').write_text(json.dumps({'A13':base,'D1':source,'changed_only':'setup.cpp diagnostic layer output'},indent=2)+'\n')
for n in ['worker_diag.py','controller_diag.py','remote_diag.py','dry_run.py','stub_solver.py','machine.py']:
 shutil.copy2(OLD/n,R/n)
# Single D1 case: no zero-initial-speed control; default A13 periodic_t4 with top initialization.
w=R/'worker_diag.py';v=w.read_text().replace("LABELS=('d1','d2')","LABELS=('d1',)");v=v.replace("(65 if label=='d1' else 0)-65-35","65-35");v=v.replace("'T17_A1B_ZERO':'1' if label=='d2' else '0',",'');w.write_text(v)
c=R/'controller_diag.py';v=c.read_text().replace("CASES=('d1','d2')","CASES=('d1',)").replace('if len(acks)<2:','if len(acks)<len(CASES):').replace('80+2*65+30','80+65+30');c.write_text(v)
io=R/'remote_diag.py';io.write_text(io.read_text().replace("LABELS=('d1','d2')","LABELS=('d1',)"))
d=R/'dry_run.py';v=d.read_text().replace("('d1','d2')","('d1',)").replace("seen=={'d1','d2'}","seen=={'d1'}");d.write_text(v)
with tarfile.open(R/'diag_stage.tar.gz','w:gz') as t:t.add(S,arcname='stage')
(R/'diag_manifest.json').write_text(json.dumps({'archive_sha256':sha(R/'diag_stage.tar.gz'),'source_sha256':source},indent=2)+'\n')
(R/'PREFLIGHT.ok').write_text(json.dumps({n:sha(R/n) for n in ['controller_diag.py','worker_diag.py','remote_diag.py','diag_stage.tar.gz','diag_manifest.json','machine.py']},indent=2)+'\n')
print('SOURCE',json.dumps(source));print('DIFF_ONLY_SETUP',all(source[n]==base[n] for n in files if n!='setup.cpp'))

#!/usr/bin/env python3
"""Build an isolated, immutable-by-convention A1b layer diagnostic."""
import pathlib,hashlib,tarfile,json,shutil,subprocess,difflib
R=pathlib.Path(__file__).resolve().parent
P=R.parent/'diagA1b2_20261119_140240'
S=R/'stage'
assert not S.exists()
with tarfile.open(P/'diag_stage.tar.gz') as t:
    for m in t:
        p=pathlib.PurePosixPath(m.name)
        assert p.parts and p.parts[0]=='stage' and '..' not in p.parts and (m.isdir() or m.isfile())
    t.extractall(R,filter='data')
setup=S/'src/setup.cpp';old=setup.read_text();s=old
s=s.replace('    const bool a1b_diag=std::getenv("T17_A1B_DIAG")', '    const bool a1b_zero=std::getenv("T17_A1B_ZERO") && std::string(std::getenv("T17_A1B_ZERO"))=="1";\n    const bool a1b_diag=std::getenv("T17_A1B_DIAG")',1)
s=s.replace('lbm.u.x[n]=units.u(target_ustar/0.4f*std::log((zm+0.024f)/0.024f)+(a1b_uniform?0.0f:dux));','lbm.u.x[n]=a1b_zero?0.0f:units.u(target_ustar/0.4f*std::log((zm+0.024f)/0.024f)+(a1b_uniform?0.0f:dux));',1)
s=s.replace('lbm.u.y[n]=units.u(a1b_uniform?0.0f:duy);','lbm.u.y[n]=a1b_zero?0.0f:units.u(a1b_uniform?0.0f:duy);',1)
a='    ledger<<"step,mass_fluid_lattice,px_fluid_lattice,ground_drag_snapshot,eligible_native_columns,ground_drag_integral_10,ground_drag_integral_50,px_before_update_fields,mass_before_update_fields\\n";'
assert a in s
s=s.replace(a,a+'\n    const char* layer_path=std::getenv("T17_LAYER_CSV");\n    if(a1b_diag && (!layer_path || !*layer_path)) print_error("T17 layer path required");\n    std::ofstream layer;\n    if(a1b_diag) { layer.open(layer_path,std::ios::out|std::ios::trunc); if(!layer) print_error("T17 cannot open layer CSV"); layer<<"step,z,px_lattice,mass_lattice\\n"; }',1)
a='        double mass=0.0,px=0.0; ulong eligible=0ul;'
assert a in s
s=s.replace(a,a+'\n        double layer_px[66]={0.0},layer_mass[66]={0.0};',1)
a='                    px+=(double)lbm.rho[n]*(double)lbm.u.x[n];'
assert a in s
s=s.replace(a,a+'\n                    if(a1b_diag) {layer_px[z]+=(double)lbm.rho[n]*(double)lbm.u.x[n];layer_mass[z]+=(double)lbm.rho[n];}',1)
a='        ledger.flush();'
assert a in s
s=s.replace(a,a+'\n        if(a1b_diag) {for(uint z=1u;z<=64u;++z) layer<<step<<","<<z<<","<<std::setprecision(17)<<layer_px[z]<<","<<layer_mass[z]<<"\\n";layer.flush();}',1)
assert s!=old
setup.write_text(s)
(R/'SOURCE.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='A1b2/setup.cpp',tofile='A1b3/setup.cpp')))
for n in ['worker_diag.py','controller_diag.py','remote_diag.py','dry_run.py','stub_solver.py','machine.py']:
    shutil.copy2(P/n,R/n)
w=R/'worker_diag.py';v=w.read_text().replace("('c1','c2')","('d1','d2')")
v=v.replace("90 if label=='c1' else 0","65 if label=='d1' else 0").replace("-90-90","-65-35").replace("if label=='c1'","if label=='d1'").replace("timeout=min(90,max(1,deadline-time.time()-90))","timeout=min(65,max(1,deadline-time.time()-35))")
v=v.replace("'T17_A1B_UNIFORM':'1' if label=='c1' else '0'","'T17_A1B_UNIFORM':'1','T17_A1B_ZERO':'1' if label=='d2' else '0','T17_LAYER_CSV':str(out/(label+'_layers.csv'))")
v=v.replace("if ledger.is_file():seal(ledger)","if ledger.is_file():seal(ledger)\n   layers=out/(label+'_layers.csv')\n   if layers.is_file():seal(layers)")
v=v.replace("if rc or not ledger.is_file():","if rc or not ledger.is_file() or not layers.is_file():")
v=v.replace("files=[ledger,sol]","with layers.open() as f: layer_rows=list(csv.DictReader(f))\n   assert len(layer_rows)==64*len(rows) and {(int(r['step']),int(r['z'])) for r in layer_rows}=={(step,z) for step in steps for z in range(1,65)}\n   files=[ledger,layers,sol]")
w.write_text(v)
c=R/'controller_diag.py';v=c.read_text().replace("('c1','c2')","('d1','d2')").replace('1.0*3600/RATE-75','0.5*3600/RATE-55').replace('1.0*3600/RATE','0.5*3600/RATE').replace('120+2*90+90','80+2*65+30').replace("'--max-hours','1'","'--max-hours','1'")
c.write_text(v)
r=R/'remote_diag.py';r.write_text(r.read_text().replace("('c1','c2')","('d1','d2')"))
d=R/'dry_run.py';v=d.read_text().replace("('c1','c2')","('d1','d2')").replace("('c1','c2')","('d1','d2')").replace("1.0*3600/5.4-75","0.5*3600/5.4-55").replace("'cap_CU':1","'cap_CU':0.5").replace("'session_seconds':3600/5.4","'session_seconds':0.5*3600/5.4").replace("'stop_reserve_s':75","'stop_reserve_s':55").replace("'build_compile_s':120,'C1_s':90,'C2_s':90,'evidence_ack_s':90","'build_compile_s':80,'D1_s':65,'D2_s':65,'evidence_ack_s':30").replace("(120+90+90+90)","(80+65+65+30)")
d.write_text(v)
st=R/'stub_solver.py';v=st.read_text().replace("print('NVIDIA A100 fixture STUB NOT HARDWARE')","print('NVIDIA A100 fixture STUB NOT HARDWARE')");v+='\nwith pathlib.Path(os.environ["T17_LAYER_CSV"]).open("w",newline="") as f:\n w=csv.writer(f);w.writerow(["step","z","px_lattice","mass_lattice"])\n for s in list(range(101))+list(range(110,steps+1,10)):\n  for z in range(1,65):w.writerow([s,z,0,32768])\n';st.write_text(v)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with tarfile.open(R/'diag_stage.tar.gz','w:gz') as t:t.add(S,arcname='stage')
(R/'diag_manifest.json').write_text(json.dumps({'archive_sha256':sha(R/'diag_stage.tar.gz'),'source_sha256':{n:sha(S/'src'/n) for n in ['setup.cpp','kernel.cpp','lbm.cpp','defines.hpp']}},indent=2)+'\n')
(R/'PREFLIGHT.ok').write_text(json.dumps({n:sha(R/n) for n in ['controller_diag.py','worker_diag.py','remote_diag.py','diag_stage.tar.gz','diag_manifest.json','machine.py']},indent=2)+'\n')
print('BUILT',R,sha(setup),sha(R/'diag_stage.tar.gz'))

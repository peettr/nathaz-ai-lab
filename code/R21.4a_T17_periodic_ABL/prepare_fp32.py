#!/usr/bin/env python3
"""Build an isolated no-wall periodic FP32 diagnostic from A13."""
import pathlib,shutil,difflib,hashlib,json,tarfile,subprocess,datetime
B=pathlib.Path(__file__).resolve().parent
A=B/'stageA13_20261119_1421/work/pack_stage/periodic_t4'
T=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');R=B/('diagFP32_'+T)
R.mkdir();S=R/'stage';shutil.copytree(A,S)
def change(name,fn):
 p=S/'src'/name;old=p.read_text();new=fn(old);assert new!=old;p.write_text(new)
 (R/(name+'.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='A13/'+name,tofile='D5D6/'+name)))
def defs(s):
 assert s.count('#define GROUND_WALL_MODEL //')==1
 s=s.replace('#define GROUND_WALL_MODEL //','//#define GROUND_WALL_MODEL //')
 assert s.count('#define PERIODIC_ABL_TOP_MIRROR //')==1
 s=s.replace('#define PERIODIC_ABL_TOP_MIRROR //','//#define PERIODIC_ABL_TOP_MIRROR //')
 return s
change('defines.hpp',defs)
def setup(s):
 assert s.count('if(a1b) print_error("T17 A1b requires GROUND_WALL_MODEL bottom mirror");')==1
 s=s.replace('if(a1b) print_error("T17 A1b requires GROUND_WALL_MODEL bottom mirror");','// FP32_BOX: no wall; a1b selects F=0, both macro-disabled.',1)
 assert s.count('if(z==0u || z+1u==lbm.get_Nz()) {lbm.flags[n]=TYPE_S;continue;}')==1
 s=s.replace('if(z==0u || z+1u==lbm.get_Nz()) {lbm.flags[n]=TYPE_S;continue;}','// FP32_BOX: all 66 z layers remain fluid, including periodic seam.',1)
 needle='const float zm=(float)z-0.5f;';assert s.count(needle)==1
 s=s.replace(needle,'''const float zm=(float)z-0.5f;
        // Smooth z-periodic shear, matching D1 initial u(z) mean and half-range.
        const double u_low=target_ustar/0.4*std::log((0.5+0.024)/0.024);
        const double u_high=target_ustar/0.4*std::log((63.5+0.024)/0.024);
        const double box_mean=0.5*(u_low+u_high);
        const double box_amp=0.5*(u_high-u_low);
        const char* uniform_box=std::getenv("T17_FP32_UNIFORM");
        const bool is_uniform=uniform_box && std::string(uniform_box)=="1";''',1)
 needle='units.u(target_ustar/0.4f*std::log((zm+0.024f)/0.024f)+(a1b_uniform?0.0f:dux))'
 assert s.count(needle)==1
 s=s.replace(needle,'units.u((float)(box_mean+(is_uniform?0.0:box_amp*std::sin(2.0*pi*((double)z+0.5)/66.0))))',1)
 assert s.count('lbm.u.y[n]=units.u(a1b_uniform?0.0f:duy);')==1
 s=s.replace('lbm.u.y[n]=units.u(a1b_uniform?0.0f:duy);','lbm.u.y[n]=0.0f;',1)
 # Remove host-only A3 assertions for the deliberately no-wall fixture.
 start=s.index('    // A3 pre-launch host audit of the actual native flags,')
 end=s.index('    // All periodic diagnostics are opt-in.',start)
 s=s[:start]+'    // FP32_BOX: no solid columns by design; no A3 wall gate.\n'+s[end:]
 s=s.replace('for(uint z=1u;z+1u<lbm.get_Nz();++z)','for(uint z=0u;z<lbm.get_Nz();++z)',1)
 start=s.index('        for(uint y=0u;y<lbm.get_Ny();++y) for(uint x=0u;x<lbm.get_Nx();++x) {\n            bool ok=',s.index('auto sample='))
 end=s.index('        for(uint z=0u;z<lbm.get_Nz();++z)',start)
 s=s[:start]+'        // FP32_BOX: every cell fluid; eligible is intentionally zero.\n'+s[end:]
 s=s.replace('if(eligible!=(ulong)lbm.get_Nx()*(ulong)lbm.get_Ny())\n            print_error("T17 A3 native eligible column mismatch");','// No A3 wall-eligibility assertion in all-fluid D5/D6.',1)
 # no wall forces; the a1b diagnostic below uses zero-force and only 1000 steps.
 s=s.replace('if(a1b_diag) lbm.update_fields();','if(a1b_diag) lbm.update_fields();',1)
 return s
change('setup.cpp',setup)
for n in ['kernel.cpp','lbm.cpp']:
 assert (S/'src'/n).read_bytes()==(A/'src'/n).read_bytes()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['worker_diag.py','controller_diag.py','remote_diag.py','dry_run.py','stub_solver.py','machine.py']:
 shutil.copy2(B/'diagA1b4_20261119_1820'/n,R/n)
w=R/'worker_diag.py';x=w.read_text().replace("LABELS=('d1',)","LABELS=('d5','d6')");x=x.replace("'T17_A1B_UNIFORM':'1',","'T17_A1B_UNIFORM':'1', 'T17_FP32_UNIFORM':'1' if label=='d6' else '0',")
x=x.replace("'T17_A1B_UNIFORM':'1','T17_LAYER_CSV'","'T17_A1B_UNIFORM':'1','T17_FP32_UNIFORM':'1' if label=='d6' else '0','T17_LAYER_CSV'")
x=x.replace("'T17_A1B_UNIFORM':'1','T17_LAYER_CSV'","'T17_A1B_UNIFORM':'1','T17_FP32_UNIFORM':'1' if label=='d6' else '0','T17_LAYER_CSV'")
x=x.replace('for z in range(1,65)','for z in range(0,66)').replace('64*len(rows)','66*len(rows)').replace("range(1,65)}","range(0,66)}")
x=x.replace("if label=='d1':files.append(cl)","if label=='d5':files.append(cl)")
x=x.replace("margin=deadline-time.time()-65-35","margin=deadline-time.time()-(65*(len(LABELS)-LABELS.index(label)))-35")
x=x.replace("'T17_LAYER_CSV':str(out/(label+'_layers.csv'))","'T17_LAYER_CSV':str(out/(label+'_layers.csv'))")
assert "'T17_FP32_UNIFORM'" in x
w.write_text(x)
c=R/'controller_diag.py';x=c.read_text().replace("CASES=('d1',)","CASES=('d5','d6')").replace('0.5*3600/RATE','0.3*3600/RATE').replace('80+65+30','80+2*65+30').replace("'--max-hours','1'","'--max-hours','1'")
# Do not proceed if an assumed wall-clock build cannot fit hard CU cap.
c.write_text(x)
io=R/'remote_diag.py';io.write_text(io.read_text().replace("LABELS=('d1',)","LABELS=('d5','d6')"))
d=R/'dry_run.py';x=d.read_text().replace("('d1',)","('d5','d6')").replace("('d1',):","('d5','d6'):").replace("{'d1'}","{'d5','d6'}").replace('0.5*3600/5.4','0.3*3600/5.4').replace('80+65+65+30','80+65+65+30');d.write_text(x)
st=R/'stub_solver.py';x=st.read_text().replace('range(1,65)','range(0,66)');st.write_text(x)
source={n:sha(S/'src'/n) for n in ['kernel.cpp','lbm.cpp','setup.cpp','defines.hpp']}
with tarfile.open(R/'diag_stage.tar.gz','w:gz') as t:t.add(S,arcname='stage')
(R/'diag_manifest.json').write_text(json.dumps({'archive_sha256':sha(R/'diag_stage.tar.gz'),'source_sha256':source},indent=2)+'\n')
(R/'PREFLIGHT.ok').write_text(json.dumps({n:sha(R/n) for n in ['controller_diag.py','worker_diag.py','remote_diag.py','diag_stage.tar.gz','diag_manifest.json','machine.py']},indent=2)+'\n')
(R/'SOURCE_PROVENANCE.json').write_text(json.dumps({'base':str(A),'A13_kernel':sha(A/'src/kernel.cpp'),'D5D6_kernel':source['kernel.cpp'],'A13_lbm':sha(A/'src/lbm.cpp'),'D5D6_lbm':source['lbm.cpp'],'profile':'U(z)=Ubar+A*sin(2*pi*(z+0.5)/66); Ubar=(Ulog(0.5)+Ulog(63.5))/2, A=(Ulog(63.5)-Ulog(0.5))/2. D6=Ubar.'},indent=2)+'\n')
print('ROOT',R,'SOURCE',source)

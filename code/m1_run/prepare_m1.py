from pathlib import Path
import tarfile, shutil, hashlib
R=Path(__file__).resolve().parent
src=R.parent/'lhigh_fix/lhigh_fixed_fixture.tar.gz'
with tarfile.open(src) as t:t.extractall(R/'reg',filter='data')
k=R/'reg/dfg_laminar_stage_FluidX3D/src/kernel.cpp'
s=k.read_text()
a='\tfor(uint k=ibb_start[n]; k<ibb_start[n+1u]; k++) {'
b='\t\tfhn[opposite]=reflected;\n\t\tibb_link_force'
c='\t}\n)+"#endif"+R(\n\n)+"#ifdef GROUND_WALL_MODEL"'
assert all(s.count(x)==1 for x in (a,b,c))
s=s.replace(a,'\tfloat ibb_mass_delta=0.0f;\n'+a,1).replace(b,'\t\tibb_mass_delta += reflected-outgoing;\n'+b,1).replace(c,'\t}\n\tfhn[0]-=ibb_mass_delta;\n)+"#endif"+R(\n\n)+"#ifdef GROUND_WALL_MODEL"',1)
k.write_text(s)
# Keep city M1 exactly as tested: source and config frozen in M1fast archive.
with tarfile.open(R.parent/'mass/M1fast.tar.gz') as t:t.extractall(R/'city',filter='data')
conf=R/'city/stage/case/conf.luwpf';s=conf.read_text();assert s.count('run_nstep = 10000')==1
conf.write_text(s.replace('run_nstep = 10000','run_nstep = 31000'))
for tag,root in [('reg',R/'reg'),('city',R/'city')]:
 with tarfile.open(R/(tag+'_m1.tar.gz'),'w:gz') as t:
  for p in root.iterdir():t.add(p,arcname=p.name)
print({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'reg_m1.tar.gz',R/'city_m1.tar.gz')})

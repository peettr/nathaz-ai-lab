from pathlib import Path
import hashlib,json,tarfile,shutil
r=Path(__file__).resolve().parent
s=r/'stage_t4'
a=s/'FluidX3D_gate0'
b=s/'FluidX3D_gate0_B'
assert not b.exists()
shutil.copytree(a,b)
def edit(p,old,new):
 t=p.read_text();assert t.count(old)==1,(p,old,t.count(old));p.write_text(t.replace(old,new))
# Only the closed periodic fixture A expands the mask. Production stays unchanged.
edit(a/'src/defines.hpp','#define WALL_GATE0 // closed-box diagnostic only','#define WALL_GATE0 // closed-box diagnostic only\n#define WALL_GATE0_ALL // all periodic ground sites eligible')
for d in (a,b):
 edit(d/'src/lbm.cpp','"\\n\t#define WALL_GATE0"','"\\n\t#define WALL_GATE0"\n#ifdef WALL_GATE0_ALL\n\t"\\n\t#define WALL_GATE0_ALL"\n#endif')
 edit(d/'src/setup.cpp','    evidence<<"step,mass,px,wall_fx_sum\\n";','    evidence<<std::setprecision(17);\n    evidence<<"step,mass,px,pz,wall_fx_sum\\n";')
 edit(d/'src/setup.cpp','double mass=0.0,px=0.0;','double mass=0.0,px=0.0,pz=0.0;')
 edit(d/'src/setup.cpp','mass+=gate.rho[n];px+=(double)gate.rho[n]*(double)gate.u.x[n];','mass+=gate.rho[n];px+=(double)gate.rho[n]*(double)gate.u.x[n];pz+=(double)gate.rho[n]*(double)gate.u.z[n];')
 edit(d/'src/setup.cpp','for(uint y=2u;y+2u<gate.get_Ny();y++) for(uint x=2u;x+2u<gate.get_Nx();x++) {','for(uint y=0u;y<gate.get_Ny();y++) for(uint x=0u;x<gate.get_Nx();x++) {')
 edit(d/'src/setup.cpp','evidence<<step<<","<<mass<<","<<px<<","<<fx<<"\\n";evidence.flush();','evidence<<step<<","<<mass<<","<<px<<","<<pz<<","<<fx<<"\\n";evidence.flush();')
 # B's name and output do not collide with A.
 if d==b:edit(d/'src/setup.cpp','/content/wall_gate0.csv','/content/wall_gate0_B.csv')
 edit(d/'src/kernel.cpp','    if((int)xyz.z+def_Oz!=def_ground_first_fluid_z || xyz.x<=1u || xyz.x+2u>=def_Nx ||','    if((int)xyz.z+def_Oz!=def_ground_first_fluid_z ||\n#ifndef WALL_GATE0_ALL\n       xyz.x<=1u || xyz.x+2u>=def_Nx ||')
 edit(d/'src/kernel.cpp','       xyz.y<=1u || xyz.y+2u>=def_Ny || (flags[n]&TYPE_BO)!=0u) return false;','       xyz.y<=1u || xyz.y+2u>=def_Ny ||\n#endif\n       (flags[n]&TYPE_BO)!=0u) return false;')
 edit(d/'src/kernel.cpp','    if((flags[j[6]]&TYPE_BO)!=TYPE_S) return false;','    if((flags[j[6]]&TYPE_BO)!=TYPE_S) return false;\n#ifdef WALL_GATE0_ALL\n    return true; // entire x/y-periodic plane; ordinary cells above are fluid\n#endif')
# Freeze bundle metadata, never mutate source under previous roots.
m=s/'manifest.json';v=json.loads(m.read_text());v['fixture_A_sha256']={p:hashlib.sha256((a/'src'/p).read_bytes()).hexdigest() for p in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp')};v['fixture_B_sha256']={p:hashlib.sha256((b/'src'/p).read_bytes()).hexdigest() for p in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp')};m.write_text(json.dumps(v,indent=2)+'\n')
archive=r/'stage_t4.tar.gz';assert not archive.exists()
with tarfile.open(archive,'w:gz') as f:f.add(s,arcname='stage_t4')
print('bundle_sha256',hashlib.sha256(archive.read_bytes()).hexdigest(), 'A/B',v['fixture_A_sha256'],v['fixture_B_sha256'])

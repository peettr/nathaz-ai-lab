#!/usr/bin/env python3
"""Freeze build6 from build5 without touching prior evidence."""
from pathlib import Path
import shutil,hashlib,subprocess,json,datetime
P=Path(__file__).resolve().parent
old=P/'build5_20261117_1156/FluidX3D_facade_v5'
root=P/('build6_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
root.mkdir(exist_ok=False)
new=root/'FluidX3D_facade_v6';shutil.copytree(old,new)
src=new/'src'
def edit(name,fn):
 p=src/name;s=p.read_text();v=fn(s);assert v!=s;p.write_text(v)
def kernel(s):
 old='''  const uint3 xyz=coordinates(n);
  if(xyz.x<=1u||xyz.x+2u>=def_Nx||xyz.y<=1u||xyz.y+2u>=def_Ny||xyz.z<=1u||xyz.z+2u>=def_Nz) return false;
  uxx j[def_velocity_set]; neighbors(n,j);'''
 # The neighbor helper already wraps coordinates in all axes. Preserve the mirror read/write block.
 assert s.count(old)==1
 s=s.replace(old,'  uxx j[def_velocity_set]; neighbors(n,j);')
 # No direct-offset accesses in facade_eligible; j[] are periodic neighbors.
 start=s.index('bool facade_eligible(');end=s.index(')+"#endif"+R(',start)
 assert 'flags[j[' in s[start:end] and '±' not in s[start:end]
 s=s.replace(')+"#ifdef WALL_GATE0"+R(\n\t, global float* ground_force',')+"#ifdef WALL_GATE0"+R(\n\t, global float* ground_force')
 needle=')+"#ifdef FORCE_FIELD"+R(\n\t, const global float* F'
 assert s.count(needle)==1
 s=s.replace(needle,')+"#ifdef FACADE_COUNT"+R(\n    , global uint* facade_link_count\n)+"#endif"+R(\n'+needle,1)
 # Every successful mirror load is one executed directed link. No atomic traffic when macro is off.
 a=s.index(')+"#ifdef FACADE_FREE_SLIP"+R(',s.index('kernel void stream_collide'))
 b=s.index(')+"#endif"+R(',a)
 part=s[a:b]
 import re
 pat=r'(    fhn\[\d+\]=load\(fi,index_f\([^;]+;)([^\n]*)'
 hits=re.findall(pat,part)
 assert len(hits)==16,len(hits)
 part=re.sub(pat,lambda m:'    { '+m.group(1)+'\n#ifdef FACADE_COUNT\n      atomic_inc((volatile global uint*)facade_link_count);\n#endif\n    }'+m.group(2),part)
 return s[:a]+part+s[b:]
edit('kernel.cpp',kernel)
def lbm(s):
 needle='#ifdef FORCE_FIELD\n\tF = Memory<float>(device, N, 3u);'
 assert s.count(needle)==1
 s=s.replace(needle,'#ifdef FACADE_COUNT\n\tfacade_link_count = Memory<uint>(device, 1u);\n\tkernel_stream_collide.add_parameters(facade_link_count);\n#endif\n'+needle,1)
 needle='#ifdef FACADE_FREE_SLIP\n\t"\\n\t#define FACADE_FREE_SLIP"\n#endif'
 assert s.count(needle)==1
 s=s.replace(needle,needle+'\n#ifdef FACADE_COUNT\n\t"\\n\t#define FACADE_COUNT"\n#endif',1)
 return s
edit('lbm.cpp',lbm)
def hpp(s):
 needle='\tMemory<fpxx> fi; // LBM density distribution functions (DDFs); only exist in device memory'
 assert s.count(needle)==1
 return s.replace(needle,needle+'\n#ifdef FACADE_COUNT\npublic:\n\tMemory<uint> facade_link_count; // test-only real device mirror-link count, reset each step\nprivate:\n#endif',1)
edit('lbm.hpp',hpp)
def setup(s):
 needle='       <<"step,M_all,fluid_rho,fluid_rho_two_step,wall_link_normal_flux_abs,wall_tangential_speed_mean,wall_faces,tangent_momentum,mirror_active_cells\\n";'
 assert s.count(needle)==1
 s=s.replace(needle,needle.replace('mirror_active_cells\\n','device_mirror_links\\n'))
 needle='        gate.run(step?1u:0u,100u);'
 assert s.count(needle)==1
 s=s.replace(needle,'#ifdef FACADE_COUNT\n        auto& count=gate.lbm_domain[0]->facade_link_count;\n        if(step) { count[0]=0u; count.write_to_device(); }\n#endif\n'+needle,1)
 needle='        fi.read_from_device();gate.rho.read_from_device();gate.u.read_from_device();'
 assert s.count(needle)==1
 s=s.replace(needle,needle+'\n#ifdef FACADE_COUNT\n        if(step) count.read_from_device();\n#endif',1)
 s=s.replace('ulong faces=0u,active=0u;','ulong faces=0u;')
 a=s.index('#ifdef FACADE_FREE_SLIP\n',s.index('void main_setup() {'));b=s.index('#endif',a)+len('#endif')
 assert 'active++' in s[a:b];s=s[:a]+s[b:]
 needle="<<','<<flux<<','<<(faces?tangent/faces:0.0)<<','<<faces<<','<<px<<','<<active<<'\\n';"
 assert s.count(needle)==1
 s=s.replace(needle,"<<','<<flux<<','<<(faces?tangent/faces:0.0)<<','<<faces<<','<<px<<','\n#ifdef FACADE_COUNT\n                 <<(step?count[0]:0u)\n#else\n                 <<0u\n#endif\n                 <<'\\n';")
 return s
edit('setup.cpp',setup)
# Keep source diff and member hashes deterministic, with the pristine T5 OFF reference.
base=P.parent/'R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off'
for label,other in [('v5',old),('T5_OFF',base)]:
 with (root/('diff_vs_'+label+'.patch')).open('w') as out:
  for name in ('kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp','defines.hpp'):
   a=other/'src'/name;b=src/name
   if not a.exists():continue
   r=subprocess.run(['diff','-u','--label',label+'/'+name,'--label','v6/'+name,str(a),str(b)],text=True,stdout=subprocess.PIPE)
   assert r.returncode in (0,1)
   out.write(r.stdout)
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={str(p.relative_to(new)):sha(p) for p in sorted(new.rglob('*')) if p.is_file()}
(root/'source_sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(root)
print('changed',[(k,manifest[k]) for k in ('src/kernel.cpp','src/lbm.cpp','src/lbm.hpp','src/setup.cpp')])

#!/usr/bin/env python3
"""Fail-closed seven-variant source check; never runs a solver."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys
R=Path(__file__).resolve().parent
S=R/'stage/FluidX3D_on/src'
B=Path('06_Logs/R21.4a_T15_second_layer_WM/continuation8b_20261119_0026')
if not B.exists():
 B=R.parents[1]/'R21.4a_T15_second_layer_WM/continuation8b_20261119_0026'
VAR={'periodic_bounce':(1,0,0,0),'periodic_t4':(1,1,0,0),'periodic_t15_k2':(1,1,1,0),'periodic_t15_k3':(1,1,1,1),'legacy_off':(0,0,0,0),'legacy_on':(0,1,1,0),'legacy_k3':(0,1,1,1)}
O=R/'seven_variants_A7_final';O.mkdir(exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
results={}
for name,(periodic,ground,second,k3) in VAR.items():
 d=O/name; shutil.copytree(S,d,ignore=shutil.ignore_patterns('*.o','*.a','*.so','*.exe'))
 defs=d/'defines.hpp';text=defs.read_text()
 for macro,enabled in [('PERIODIC_ABL_GROUND',periodic),('GROUND_WALL_MODEL',ground),('SECOND_LAYER_WM',second)]:
  off='//#define '+macro+' ';on='#define '+macro+' '
  if enabled and off in text:text=text.replace(off,on,1)
  if not enabled and on in text:text=text.replace(on,off,1)
  assert any(line.startswith(on) for line in text.splitlines())==bool(enabled),(name,macro)
 defs.write_text(text)
 if k3:
  p=d/'kernel.cpp';text=p.read_text()
  old='log((1.5f+def_ground_z0_lattice)/def_ground_z0_lattice)';assert old in text
  text=text.replace(old,'log((2.5f+def_ground_z0_lattice)/def_ground_z0_lattice)')
  old='const ulong b=a+(ulong)xy;\n        if(first==0u || first+1u>=def_Nz ||'
  assert old in text
  text=text.replace(old,'const ulong b=a+2ul*(ulong)xy; // k=3 sensitivity: 2.5 m above numerical wall\n        if(first==0u || first+2u>=def_Nz ||')
  old='if(first==0u || first+1u>=def_Nz) { new_stress[col]=0.0f;new_stress[xy+col]=0.0f;return; }\n    const ulong a=(ulong)col+(ulong)first*(ulong)xy, b=a+(ulong)xy;'
  assert old in text
  text=text.replace(old,'if(first==0u || first+2u>=def_Nz) { new_stress[col]=0.0f;new_stress[xy+col]=0.0f;return; }\n    const ulong a=(ulong)col+(ulong)first*(ulong)xy, b=a+2ul*(ulong)xy;')
  text=text.replace('const float logwall=log((2.5f+def_ground_z0_lattice)/def_ground_z0_lattice);','const float logwall=log((2.5f+def_ground_z0_lattice)/def_ground_z0_lattice); // k=3 sensitivity only',1)
  old='\tfloat applied_ground_fx=0.0f;\n\tif(ground_first_fluid) {'
  new='\tfloat applied_ground_fx=0.0f;\n\t\t) + "#ifdef SECOND_LAYER_WM" + R(\n\tfloat applied_ground_fy=0.0f;\n\tfloat applied_ground_tau_abs=0.0f;\n\t\t) + "#endif" + R(\n\tif(ground_first_fluid) {'
  assert text.count(old)==1
  text=text.replace(old,new,1)
  old='        float applied_ground_fy=0.0f;\n        float applied_ground_tau_abs=0.0f;\n        const uint col=ground_xyz.x+def_Nx*ground_xyz.y;'
  assert text.count(old)==1
  text=text.replace(old,'        const uint col=ground_xyz.x+def_Nx*ground_xyz.y;',1)
  p.write_text(text)
 result={'macros':dict(zip(('periodic','ground','second','k3'),(periodic,ground,second,k3)))}
 for fn in ('kernel.cpp','lbm.cpp','setup.cpp'):
  cmd=['g++','-std=c++17','-fsyntax-only','-I'+str(d),'-I'+str(d/'OpenCL/include'),'-I'+str(d/'X11/include'),str(d/fn)]
  q=subprocess.run(cmd,capture_output=True,text=True)
  (d/(fn+'.syntax.log')).write_text(' '.join(cmd)+'\n'+q.stdout+q.stderr+'\nexit='+str(q.returncode)+'\n')
  result[fn+'_syntax_exit']=q.returncode
  if q.returncode:break
 if all(result.get(f+'_syntax_exit')==0 for f in ('kernel.cpp','lbm.cpp','setup.cpp')):
  cmd=['g++','-std=c++17','-O0','-I'+str(d),'-I'+str(d/'OpenCL/include'),str(d/'kernel.cpp'),str(R/'emit_kernel.cpp'),'-o',str(d/'emit')]
  q=subprocess.run(cmd,capture_output=True,text=True)
  (d/'emitter.log').write_text(' '.join(cmd)+'\n'+q.stdout+q.stderr+'\nexit='+str(q.returncode)+'\n')
  result['emitter_exit']=q.returncode
  if q.returncode==0:
   q=subprocess.run([str(d/'emit'),str(d/'generated.cl')],capture_output=True,text=True)
   (d/'generation.log').write_text(q.stdout+q.stderr+'\nexit='+str(q.returncode)+'\n')
   result['generation_exit']=q.returncode
   if q.returncode==0: result['generated_sha256']=sha(d/'generated.cl')
 if name.startswith('legacy_') and result.get('generation_exit')==0:
  old=B/(name.removeprefix('legacy_')+'_new_kernel_container.cl')
  if not old.exists():
   matches=list(B.rglob(old.name));old=matches[0] if len(matches)==1 else old
  result['reference_path']=str(old)
  if old.exists():
   result['reference_sha256']=sha(old)
   result['byte_equal']=old.read_bytes()==(d/'generated.cl').read_bytes()
 results[name]=result
 print(name,json.dumps(result,ensure_ascii=False),flush=True)
(R/'PREFLIGHT_RESULT_A7_final.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
if not all(all(v.get(f+'_syntax_exit')==0 for f in ('kernel.cpp','lbm.cpp','setup.cpp')) and v.get('generation_exit')==0 and (not k.startswith('legacy_') or v.get('byte_equal') is True) for k,v in results.items()):sys.exit(2)

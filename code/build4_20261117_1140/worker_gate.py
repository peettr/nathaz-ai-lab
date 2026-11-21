#!/usr/bin/env python3
"""Build and run T9b build4 ordered GPU gates. No city production."""
import os, pathlib, subprocess, tarfile, hashlib, json, shutil, csv, traceback, time
R=pathlib.Path('/content/t9b4'); O=R/'out'; SRC=R/'stage/FluidX3D_facade_v4'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ready(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n');print('READY',p.name,flush=True)
def run(args,cwd,tag,env=None,limit=1600):
 p=O/(tag+'.log')
 with p.open('x') as f:r=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=limit)
 ready(p);print('EXIT',tag,r.returncode,flush=True)
 if r.returncode:raise RuntimeError(f'{tag}: solver/build exit {r.returncode}')
def analyze(p,channel):
 rows=list(csv.DictReader(p.open()));assert len(rows)==(1001 if channel else 301),len(rows)
 assert [int(r['step']) for r in rows]==list(range(len(rows)))
 for row in rows:
  for k in ('M_all','fluid_rho','fluid_rho_two_step','wall_link_normal_flux_abs','wall_tangential_speed_mean','tangent_momentum'):
   assert __import__('math').isfinite(float(row[k])),(p,k,row['step'])
 return rows
def main():
 R.mkdir(exist_ok=False);O.mkdir(); (R/'stage').mkdir()
 arc=pathlib.Path('/content/t9b4_source.tar.gz');manifest=json.loads(pathlib.Path('/content/t9b4_manifest.json').read_text())
 assert sha(arc)==manifest['archive_sha256']
 with tarfile.open(arc) as t:
  for m in t.getmembers():assert (m.name=='FluidX3D_facade_v4' or m.name.startswith('FluidX3D_facade_v4/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()),m.name
  t.extractall(R/'stage',filter='data')
 for name,h in manifest['members'].items():assert sha(SRC/name)==h,name
 verdict={'created':time.time(),'cube':{},'channels':{},'source_sha256':manifest['archive_sha256']}
 for state in ('off','on'):
  d=R/('cube_'+state);shutil.copytree(SRC,d)
  defines=d/'src/defines.hpp';s=defines.read_text();needle='//#define FACADE_FREE_SLIP // T9b-build default OFF';assert s.count(needle)==1
  if state=='on':s=s.replace(needle,'#define FACADE_FREE_SLIP // T9b-build ON')
  assert '#define UPDATE_FIELDS' in s
  s=s.replace(needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON', (needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON')+'\n#define FACADE_CUBE_GATE')
  defines.write_text(s)
  run(['make','Linux','-j8'],d,'build_'+state,limit=1200)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH','')}
  env['LUW_CAPTURE_CL']=str(O/(state+'_cube_actual_opencl.cl'))
  p=O/(state+'_cube_trace.csv');env['T9B_GATE_OUTPUT']=str(p)
  run([str(d/'bin/FluidX3D')],d,'solver_'+state,env,limit=900)
  for v in (p,O/(state+'_cube_actual_opencl.cl')):assert v.stat().st_size;ready(v)
  rows=analyze(p,False); masses=[float(r['M_all']) for r in rows];ref=masses[50]
  jump=(masses[1]-masses[0])/masses[0]
  if state=='off':
   metric=max(abs(x-ref) for x in masses[50:])/abs(ref)
   ok=metric<=1e-6;verdict['cube'][state]={'jump_0_1':jump,'max_relative_change_t50_on':metric,'passed':ok}
  else:
   import numpy as np
   y=np.array(masses[50:],dtype=float)/ref; x=np.arange(50,len(masses),dtype=float)
   slope=float(np.polyfit(x,y,1)[0]*1000)
   swing=float(y.max()-y.min())
   ok=abs(slope)<=1e-5 and swing<=1e-5
   verdict['cube'][state]={'jump_0_1':jump,'relative_slope_1000':slope,'relative_peak_to_peak':swing,'passed':ok}
  v=O/('gate_verdict_cube_'+state+'.json');v.write_text(json.dumps(verdict,indent=2)+'\n');ready(v)
  if not ok:raise RuntimeError('cube '+state+' gate failed')
 # The two wall axes use the identical source and corresponding compiler macro state.
 for wall in ('x','y'):
  for state in ('off','on'):
   d=R/('cube_'+state);p=O/(f'channel_{wall}_{state}_trace.csv')
   env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(p),'T9B_GATE_SHAPE':'channel'}
   if wall=='y':env['T9B_WALL_Y']='1'
   run([str(d/'bin/FluidX3D')],d,f'channel_{wall}_{state}',env,limit=1000)
   ready(p);rows=analyze(p,True)
   m0=float(rows[0]['tangent_momentum']);end=float(rows[-1]['tangent_momentum']);assert m0>0
   drift=abs(end-m0)/m0;ratio=end/m0
   ok=drift<=1e-5 if state=='on' else ratio<=0.9
   verdict['channels'][wall+'_'+state]={'initial':m0,'final':end,'relative_change':drift,'ratio':ratio,'passed':ok}
   v=O/(f'gate_verdict_channel_{wall}_{state}.json');v.write_text(json.dumps(verdict,indent=2)+'\n');ready(v)
   if not ok:raise RuntimeError('channel '+wall+' '+state+' gate failed')
 # Both physical gates passed; only now enter the city compilation/closed-state gates.
 import numpy as np
 from remote_worker_run2 import vtk_map
 from t5_reference_worker import sampled
 base=pathlib.Path('/content/t9b2_stage.tar.gz');bm=json.loads(pathlib.Path('/content/t9b2_archive.json').read_text())
 assert sha(base)==bm['archive_sha256']; legacy=R/'legacy';legacy.mkdir()
 with tarfile.open(base) as t:
  for m in t.getmembers():assert (m.name=='stage' or m.name.startswith('stage/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir())
  t.extractall(legacy,filter='data')
 for name,h in bm['members'].items():assert sha(legacy/'stage'/name)==h,name
 case=legacy/'stage/case';ref=json.loads((legacy/'stage/B2u_reference_points.json').read_text())
 for state in ('on','off'):
  d=R/('city_'+state);shutil.copytree(SRC,d)
  defines=d/'src/defines.hpp';s=defines.read_text();needle='//#define FACADE_FREE_SLIP // T9b-build default OFF';assert s.count(needle)==1
  if state=='on':s=s.replace(needle,'#define FACADE_FREE_SLIP // T9b-build ON')
  defines.write_text(s);run(['make','Linux','-j8'],d,'city_build_'+state,limit=1200)
  dest=R/('city_case_'+state);shutil.copytree(case,dest)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'LUW_CAPTURE_CL':str(O/(state+'_city_actual_opencl.cl')),'LUW_EXPORT_FLAGS':str(dest/'native_flags.bin')}
  if state=='on':env['LUW_FLAGS_ONLY']='1'
  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200 if state=='off' else 900)
  cl=O/(state+'_city_actual_opencl.cl');assert cl.stat().st_size;ready(cl)
  flags=dest/'native_flags.bin';assert flags.stat().st_size==500*500*270
  raw=np.memmap(flags,dtype=np.uint8,mode='r',shape=(270,500,500))
  np.savez_compressed(O/(state+'_city_flags.npz'),flags=raw);ready(O/(state+'_city_flags.npz'))
  if state=='off':
   vtk=list((dest/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,vtk
   v=vtk_map(vtk[0]);assert v['dims']==(500,500,270) and v['origin']==(0.,0.,-20.)
   rows=[{'id':int(p['id']),'obs':float(p['after']),**sampled(v,p)} for p in ref['rows']]
   assert len(rows)==80 and {p['id'] for p in rows}==set(range(1,81))
   p=O/'points80.json';p.write_text(json.dumps({'label':'E_s101_off','uref':ref['uref'],'rows':rows,'source_vtk_sha256':sha(vtk[0]),'sample_height_above_wall_m':2.0,'vtk_label_z_m':2.5},indent=2)+'\n');ready(p)
   target='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
   verdict['gate1']={'sha256':sha(p),'target':target,'passed':sha(p)==target}
   q=O/'gate1.json';q.write_text(json.dumps(verdict['gate1'],indent=2)+'\n');ready(q)
   if not verdict['gate1']['passed']:raise RuntimeError('gate1 bitwise failure')
 (O/'run.done').write_text('cube/channel and city off hash passed; flag comparison pending host\n');ready(O/'run.done')
if __name__=='__main__':
 try:main()
 except BaseException:
  O.mkdir(parents=True,exist_ok=True);p=O/'run.failed';p.write_text(traceback.format_exc());ready(p);raise

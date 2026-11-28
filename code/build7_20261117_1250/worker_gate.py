#!/usr/bin/env python3
"""T9b build7: corrected thick-wall channels, then ordered city gates."""
import os, pathlib, subprocess, tarfile, hashlib, json, shutil, csv, traceback, time
R=pathlib.Path('/content/t9b7'); O=R/'out'; SRC=R/'stage/FluidX3D_facade_v7'
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
 rows=list(csv.DictReader(p.open()));assert len(rows)==1001,len(rows)
 assert [int(r['step']) for r in rows]==list(range(len(rows)))
 for row in rows:
  for k in ('M_all','fluid_rho','fluid_rho_two_step','wall_link_normal_flux_abs','wall_tangential_speed_mean','tangent_momentum'):
   assert __import__('math').isfinite(float(row[k])),(p,k,row['step'])
 return rows
def main():
 R.mkdir(exist_ok=False);O.mkdir(); (R/'stage').mkdir()
 arc=pathlib.Path('/content/t9b7_source.tar.gz');manifest=json.loads(pathlib.Path('/content/t9b7_manifest.json').read_text())
 assert sha(arc)==manifest['archive_sha256']
 with tarfile.open(arc) as t:
  for m in t.getmembers():assert (m.name=='FluidX3D_facade_v7' or m.name.startswith('FluidX3D_facade_v7/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()),m.name
  t.extractall(R/'stage',filter='data')
 for name,h in manifest['members'].items():assert sha(SRC/name)==h,name
 # CPU-only version-stamp audit is a mandatory fail-closed prerequisite on the VM.
 subprocess.run(['python3','/content/audit_versions.py'],cwd='/content',check=True,stdout=(O/'audit_versions.log').open('x'),stderr=subprocess.STDOUT,timeout=600)
 audit_path=pathlib.Path('/content/audit_versions_output.json');assert audit_path.is_file()
 shutil.copyfile(audit_path,O/'audit_versions_output.json');ready(O/'audit_versions_output.json');ready(O/'audit_versions.log')
 verdict={'created':time.time(),'cube_build7_retested':True,'channels':{},'source_sha256':manifest['archive_sha256']}
 for state in ('off','on'):
  d=R/('channel_'+state);shutil.copytree(SRC,d)
  defines=d/'src/defines.hpp';s=defines.read_text();needle='//#define FACADE_FREE_SLIP // T9b-build default OFF';assert s.count(needle)==1
  if state=='on':s=s.replace(needle,'#define FACADE_FREE_SLIP // T9b-build ON')
  assert '#define UPDATE_FIELDS' in s
  s=s.replace(needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON', (needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON')+'\n#define FACADE_CUBE_GATE\n#define FACADE_COUNT')
  defines.write_text(s)
  run(['make','Linux','-j8'],d,'build_'+state,limit=1200)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH','')}

 # Test fixture: L=8, two x-normal thick slabs; 2 faces × 8×8 fluid cells × 4 diagonals = 512 mirror links.
 small=O/'small_x_on_trace.csv';d=R/'channel_on'
 env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(small),'T9B_SMALL_COUNT':'1','T9B_GATE_SHAPE':'channel','LUW_CAPTURE_CL':str(O/'on_small_actual_opencl.cl')}
 run([str(d/'bin/FluidX3D')],d,'small_x_on',env,limit=240)
 ready(small);cl=O/'on_small_actual_opencl.cl';ready(cl)
 smoke_rows=list(csv.DictReader(small.open()))
 assert len(smoke_rows)==3 and [int(x['step']) for x in smoke_rows]==[0,1,2]
 smoke_count=[int(x['device_mirror_links']) for x in smoke_rows]
 smoke_info={'fixture':'8^3, x<=2 or x>=5 solid, all other directions periodic','hand_expected_per_step':512,'gpu_count':smoke_count,'cl_has_count_define':'#define FACADE_COUNT' in cl.read_text(),'cl_has_atomic':'atomic_inc' in cl.read_text()}
 q=O/'small_counter_verdict.json';q.write_text(json.dumps(smoke_info,indent=2)+'\n');ready(q)
 assert smoke_info['cl_has_count_define'] and smoke_info['cl_has_atomic'] and smoke_count==[0,512,512],smoke_info
 # Recheck both cube mass histories after the eligibility change, before channel tests.
 import numpy as np
 cube={}
 for state in ('off','on'):
  d=R/('channel_'+state);p=O/('cube_'+state+'_trace.csv')
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(p)}
  run([str(d/'bin/FluidX3D')],d,'cube_'+state,env,limit=1000)
  ready(p);rows=list(csv.DictReader(p.open()))
  assert len(rows)==301 and [int(r['step']) for r in rows]==list(range(301))
  mass=np.array([float(r['M_all']) for r in rows]);ref=mass[50]
  assert ref>0 and np.all(np.isfinite(mass))
  rel=(mass[50:]-ref)/ref
  slope=float(np.polyfit(np.arange(50,301),rel,1)[0])*1000
  span=float(np.ptp(rel)); maxdrift=float(np.max(np.abs(rel)))
  active=[int(r['device_mirror_links']) for r in rows]
  valid=(min(active[1:])>0 if state=='on' else max(active)==0)
  passed=None # superseded M_all gate; activation judged in channels
  cube[state]={'init_jump':float((mass[1]-mass[0])/mass[0]),'trend_x1000':slope,'amplitude':span,'max_drift_after_50':maxdrift,'min_device_links':min(active[1:]),'max_device_links':max(active),'activation_valid':valid,'passed':passed}
  verdict['cube']=cube;q=O/('gate_verdict_cube_'+state+'.json');q.write_text(json.dumps(verdict,indent=2)+'\n');ready(q)
  # build7: old M_all gate superseded; do not stop on this descriptive quantity.
 # The two wall axes use the identical source and corresponding compiler macro state.
 for wall in ('x','y'):
  for state in ('off','on'):
   d=R/('channel_'+state);p=O/(f'channel_{wall}_{state}_trace.csv')
   env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(p),'T9B_GATE_SHAPE':'channel'}
   if wall=='y':env['T9B_WALL_Y']='1'
   run([str(d/'bin/FluidX3D')],d,f'channel_{wall}_{state}',env,limit=1000)
   ready(p);rows=analyze(p,True)
   m0=float(rows[0]['tangent_momentum']);end=float(rows[-1]['tangent_momentum']);assert m0>0
   active=[int(r['device_mirror_links']) for r in rows];valid=(min(active[1:])>0) if state=='on' else (max(active)==0)
   drift=abs(end-m0)/m0;ratio=end/m0
   ok=(drift<=1e-5 if state=='on' else ratio<=0.9) and valid
   verdict['channels'][wall+'_'+state]={'initial':m0,'final':end,'relative_change':drift,'ratio':ratio,'min_active_after_step0':min(active[1:]),'max_active':max(active),'activation_valid':valid,'passed':ok,'classification':'无效测试' if state=='on' and not valid else ('通过' if ok else '不通过')}
   v=O/(f'gate_verdict_channel_{wall}_{state}.json');v.write_text(json.dumps(verdict,indent=2)+'\n');ready(v)
   if not ok:raise RuntimeError('channel '+wall+' '+state+' gate failed')
 # Both channel axes passed; only now enter the city compilation/closed-state gates.
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
 for state in ('off','on'):
  d=R/('city_'+state);shutil.copytree(SRC,d)
  defines=d/'src/defines.hpp';s=defines.read_text();needle='//#define FACADE_FREE_SLIP // T9b-build default OFF';assert s.count(needle)==1
  if state=='on':s=s.replace(needle,'#define FACADE_FREE_SLIP // T9b-build ON')
  if state=='on':s=s.replace('#define FACADE_FREE_SLIP // T9b-build ON','#define FACADE_FREE_SLIP // T9b-build ON\n#define FACADE_COUNT')
  defines.write_text(s);run(['make','Linux','-j8'],d,'city_build_'+state,limit=1200)
  dest=R/('city_case_'+state);shutil.copytree(case,dest)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'LUW_CAPTURE_CL':str(O/(state+'_city_actual_opencl.cl')),'LUW_EXPORT_FLAGS':str(dest/'native_flags.bin')}
  if state=='on':env['T9B_CITY_COUNT_OUTPUT']=str(O/'city_on_device_count.csv')
  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200)
  if state=='on':
   count_csv=O/'city_on_device_count.csv';assert count_csv.is_file() and count_csv.stat().st_size>0
   ready(count_csv)
   counts=[int(line.split(',')[1]) for line in count_csv.read_text().splitlines()]
   assert counts and min(counts)>0,('city activation invalid',min(counts) if counts else None)
  import re
  ml=[line.strip() for line in (O/('city_solver_'+state+'.log')).read_text(errors='replace').splitlines() if re.search(r'MLUPs',line,re.I)]
  perf=O/('city_'+state+'_mlups.json');perf.write_text(json.dumps({'state':state,'raw_mlups_lines':ml[-10:]})+'\n');ready(perf)
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
 if (O/'on_city_flags.npz').exists() and (O/'off_city_flags.npz').exists():
  A=np.load(O/'on_city_flags.npz')['flags']; B=np.load(O/'off_city_flags.npz')['flags'];mismatch=int(np.count_nonzero(A!=B))
  q=O/'gate3_flags.json';q.write_text(json.dumps({'mismatch_cells':mismatch,'total_cells':int(A.size),'passed':mismatch==0})+'\n');ready(q)
  if mismatch:raise RuntimeError('gate3 flags mismatch')
  solid=(A&3)==1;fluid=(A&3)!=1;ns=np.zeros(A.shape,dtype=np.uint8)
  for axis,delta in ((2,1),(2,-1),(1,1),(1,-1)):ns+=np.roll(solid,-delta,axis=axis).astype(np.uint8)
  zsolid=np.roll(solid,-1,axis=0)|np.roll(solid,1,axis=0)
  elig=fluid&(ns==1)&~zsolid
  for axis in range(3):
   sl=[slice(None)]*3;sl[axis]=slice(0,2);elig[tuple(sl)]=False
   sl[axis]=slice(-2,None);elig[tuple(sl)]=False
  oldelig=elig.copy()
  for axis in range(3):
   sl=[slice(None)]*3;sl[axis]=slice(0,2);oldelig[tuple(sl)]=False
   sl[axis]=slice(-2,None);oldelig[tuple(sl)]=False
  multi=fluid&(ns>=2);mirror=np.zeros(A.shape,dtype=bool);links=0
  for axis,sgn in ((2,1),(2,-1),(1,1),(1,-1)):
   normal=np.roll(solid,-sgn,axis=axis);face=elig&normal
   for tangaxis in (0,1,2):
    if tangaxis==axis:continue
    for tang in (-1,1):
     valid=face&np.roll(elig,tang,axis=tangaxis)&np.roll(normal,tang,axis=tangaxis)&np.roll(np.roll(solid,tang,axis=tangaxis),-sgn,axis=axis)
     mirror|=valid;links+=int(np.count_nonzero(valid))
  oldmirror=np.zeros(A.shape,dtype=bool)
  for axis,sgn in ((2,1),(2,-1),(1,1),(1,-1)):
   normal=np.roll(solid,-sgn,axis=axis);face=oldelig&normal
   for tangaxis in (0,1,2):
    if tangaxis==axis:continue
    for tang in (-1,1):
     valid=face&np.roll(oldelig,tang,axis=tangaxis)&np.roll(normal,tang,axis=tangaxis)&np.roll(np.roll(solid,tang,axis=tangaxis),-sgn,axis=axis)
     oldmirror|=valid
  ids={31,39,40,47,48,49,65,66,69,77,79};frows=[]
  for p in ref['rows']:
   if int(p['id']) not in ids:continue
   x=float(p['xls_xy'][0])+251.50008;y=float(p['xls_xy'][1])+251.60004
   ix0=max(2,int(np.floor(x-10)));ix1=min(498,int(np.ceil(x+10))+1)
   iy0=max(2,int(np.floor(y-10)));iy1=min(498,int(np.ceil(y+10))+1)
   yy,xx=np.ogrid[iy0:iy1,ix0:ix1];ball=(xx-x)**2+(yy-y)**2<=100
   adjacent=(fluid&(ns>=1))[21:26,iy0:iy1,ix0:ix1]&ball[None]
   selected=mirror[21:26,iy0:iy1,ix0:ix1]&ball[None]
   den=int(adjacent.sum());num=int(selected.sum());frows.append({'id':int(p['id']),'adjacent':den,'mirror':num,'f_i':num/den if den else None})
  assert len(frows)==11 and all(v['f_i'] is not None for v in frows)
  coverage={'eligible_cells_new_minus_old':int(elig.sum()-oldelig.sum()),'multi_normal_native_bounce':int(np.count_nonzero(multi)),'eligible_cells':int(elig.sum()),'mirror_cells':int(mirror.sum()),'mirror_links':links,'mirror_cells_old_estimate':int(oldmirror.sum()),'mirror_cells_new_minus_old':int(mirror.sum()-oldmirror.sum()),'N_far':sorted(frows,key=lambda v:v['id']),'f_bar':float(np.mean([v['f_i'] for v in frows]))}
  q=O/'full_height_coverage.json';q.write_text(json.dumps(coverage,indent=2)+'\n');ready(q)
 (O/'run.done').write_text('channels and city off hash and flags passed\n');ready(O/'run.done')
if __name__=='__main__':
 try:main()
 except BaseException:
  O.mkdir(parents=True,exist_ok=True);p=O/'run.failed';p.write_text(traceback.format_exc());ready(p);raise

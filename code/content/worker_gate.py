#!/usr/bin/env python3
"""T9b build16: frozen v11 y-channel and cube A; conditional city B."""
import os, pathlib, subprocess, tarfile, hashlib, json, shutil, csv, traceback, time
R=pathlib.Path('/content/t9b16'); O=R/'out'; SRC=R/'stage/FluidX3D_facade_v11'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ready(p):
 (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n');print('READY',p.name,flush=True)
def run(args,cwd,tag,env=None,limit=1600):
 p=O/(tag+'.log')
 try:
  deadline=json.loads(pathlib.Path('/content/t9b16_budget.json').read_text())['deadline']
  with p.open('x') as f:r=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=max(1,min(limit,deadline-time.time()-150)))
 except BaseException:
  if p.exists():ready(p)
  raise
 ready(p);print('EXIT',tag,r.returncode,flush=True)
 if r.returncode:raise RuntimeError(f'{tag}: solver/build exit {r.returncode}')
def build_solver(d,tag):
 run(['make','Linux','-j8'],d,tag,limit=1200)
 # Integration fixture only. Production launcher removes this variable.
 stub=os.getenv('T9B_PREFLIGHT_SOLVER')
 if stub:
  assert not pathlib.Path('/content/t9b16_upload.json').exists()
  exe=d/'bin/FluidX3D';assert exe.is_file() and os.access(exe,os.X_OK)
  shutil.copyfile(stub,exe)
  print('LOCAL_ONLY replaced compiled solver',exe,flush=True)
def analyze(p,channel):
 rows=list(csv.DictReader(p.open()));assert len(rows)==1001,len(rows)
 assert [int(r['step']) for r in rows]==list(range(len(rows)))
 for row in rows:
  for k in ('M_all','fluid_rho','fluid_rho_two_step','wall_link_normal_flux_abs','wall_tangential_speed_mean','tangent_momentum'):
   assert __import__('math').isfinite(float(row[k])),(p,k,row['step'])
 return rows
def budget_guard(required_seconds, stage):
 b=json.loads(pathlib.Path('/content/t9b16_budget.json').read_text())
 if time.time()+required_seconds > b['deadline']-130:
  raise RuntimeError('budget stop before '+stage+': need '+str(required_seconds)+' s plus 130 s teardown reserve')
def main():
 R.mkdir(exist_ok=False);O.mkdir(); (R/'stage').mkdir()
 arc=pathlib.Path('/content/t9b12_source.tar.gz');manifest=json.loads(pathlib.Path('/content/t9b12_manifest.json').read_text())
 assert sha(arc)==manifest['archive_sha256']
 with tarfile.open(arc) as t:
  for m in t.getmembers():assert (m.name=='FluidX3D_facade_v11' or m.name.startswith('FluidX3D_facade_v11/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()),m.name
  t.extractall(R/'stage',filter='data')
 for name,h in manifest['members'].items():assert sha(SRC/name)==h,name
 verdict={'created':time.time(),'channels':{},'source_sha256':manifest['archive_sha256'],'stage':'A'}
 for state in ('off','on'):
  d=R/('channel_'+state);shutil.copytree(SRC,d)
  defines=d/'src/defines.hpp';s=defines.read_text();needle='//#define FACADE_FREE_SLIP // T9b-build default OFF';assert s.count(needle)==1
  if state=='on':s=s.replace(needle,'#define FACADE_FREE_SLIP // T9b-build ON')
  assert '#define UPDATE_FIELDS' in s
  s=s.replace(needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON', (needle if state=='off' else '#define FACADE_FREE_SLIP // T9b-build ON')+'\n#define FACADE_CUBE_GATE')
  defines.write_text(s)
  build_solver(d,'build_'+state)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH','')}

 # The two wall axes use the identical source and corresponding compiler macro state.
 for wall in ('y',):
  for state in ('off','on'):
   d=R/('channel_'+state);p=O/(f'channel_{wall}_{state}_trace.csv')
   env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'T9B_GATE_OUTPUT':str(p),'T9B_GATE_SHAPE':'channel'}
   if wall=='y':env['T9B_WALL_Y']='1'
   run([str(d/'bin/FluidX3D')],d,f'channel_{wall}_{state}',env,limit=1000)
   ready(p);rows=analyze(p,True)
   m0=float(rows[0]['tangent_momentum']);end=float(rows[-1]['tangent_momentum']);assert m0>0
   drift=(end-m0)/m0;ratio=end/m0
   series=[(float(row['tangent_momentum'])-m0)/m0 for row in rows]
   ok=(-1e-5<=min(series) and max(series)<=1e-4 if state=='on' else ratio<=0.9)
   verdict['channels'][wall+'_'+state]={'initial':m0,'final':end,'relative_change':drift,'ratio':ratio,'min_relative':min(series),'max_relative':max(series),'trace_sha256':sha(p),'passed':ok}
   v=O/(f'gate_verdict_channel_{wall}_{state}.json');v.write_text(json.dumps(verdict,indent=2)+'\n');ready(v)
   if not ok:raise RuntimeError('channel '+wall+' '+state+' gate failed')
  if verdict['channels'][wall+'_off']['trace_sha256']==verdict['channels'][wall+'_on']['trace_sha256']:
   raise RuntimeError('channel '+wall+' on/off traces identical')
 # Cube histories are descriptive only, after both y-channel gates.
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
  cube[state]={'init_jump':float((mass[1]-mass[0])/mass[0]),'trend_x1000':slope,'amplitude':span,'max_drift_after_50':maxdrift,'trace_sha256':sha(p),'gate':'descriptive_only'}
  verdict['cube']=cube;q=O/('gate_verdict_cube_'+state+'.json');q.write_text(json.dumps(verdict,indent=2)+'\n');ready(q)
  # build9: old M_all gate superseded; do not stop on this descriptive quantity.
 verdict['stage']='A_passed';q=O/'stage_A_verdict.json';q.write_text(json.dumps(verdict,indent=2)+'\n');ready(q)
 # Both y-channel branches passed; only now enter the city compilation/closed-state gates.
 budget_guard(2930,'B city full and two short runs')
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
  defines.write_text(s);build_solver(d,'city_build_'+state)
  dest=R/('city_case_'+state);shutil.copytree(case,dest)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH',''),'LUW_CAPTURE_CL':str(O/(state+'_city_actual_opencl.cl')),'LUW_EXPORT_FLAGS':str(dest/'native_flags.bin')}
  if state=='on':env['LUW_FLAGS_ONLY']='1'
  if state=='off':budget_guard(2800,'B full s101 off')
  run([str(d/'bin/FluidX3D'),str(dest/'conf.luwpf')],dest,'city_solver_'+state,env,limit=4200)
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
  elig=((A&3)==0)&(ns==1)&~zsolid
  oldelig=elig.copy()
  for axis in range(3):
   sl=[slice(None)]*3;sl[axis]=slice(0,2);oldelig[tuple(sl)]=False
   sl=[slice(None)]*3;sl[axis]=slice(-2,None);oldelig[tuple(sl)]=False
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
 # City functional activation: independently run BOTH 2000-step variants with
 # the same seeds and sample the same 80 physical points from their mean fields.
 verdict['stage']='B_short';short={}
 for state in ('off','on'):
  budget_guard(340 if state=='off' else 170,'B city 2000 '+state)
  d=R/('city_'+state);dest=R/('city_2000_'+state);shutil.copytree(case,dest)
  config=dest/'conf.luwpf';text=config.read_text()
  assert text.count('run_nstep = 31000')==1 and text.count('purge_avg = 20000')==1
  text=text.replace('run_nstep = 31000','run_nstep = 2000').replace('purge_avg = 20000','purge_avg = 1000')
  config.write_text(text)
  staged=O/(f'city_2000_{state}_conf.luwpf');staged.write_text(text);ready(staged)
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.getenv('LD_LIBRARY_PATH','')}
  run([str(d/'bin/FluidX3D'),str(config)],dest,'city_2000_'+state,env,limit=1400)
  import re
  ml=[line.strip() for line in (O/('city_2000_'+state+'.log')).read_text(errors='replace').splitlines() if re.search(r'MLUPs',line,re.I)]
  perf=O/('city_2000_'+state+'_mlups.json');perf.write_text(json.dumps({'state':state,'raw_mlups_lines':ml[-10:]})+'\n');ready(perf)
  vtk=list((dest/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,vtk
  v=vtk_map(vtk[0]);assert v['dims']==(500,500,270) and v['origin']==(0.,0.,-20.)
  rows=[{'id':int(p['id']),**sampled(v,p)} for p in ref['rows']]
  assert len(rows)==80 and {p['id'] for p in rows}==set(range(1,81))
  out=O/(f'city_2000_{state}_points80.json');out.write_text(json.dumps({'state':state,'steps':2000,'avg_window':1000,'avg_stride':40,'source_vtk_sha256':sha(vtk[0]),'rows':rows},indent=2)+'\n');ready(out)
  short[state]=rows
 assert [p['id'] for p in short['off']]==[p['id'] for p in short['on']]
 differences=[p['id'] for p,q in zip(short['off'],short['on']) if p['Su']!=q['Su']]
 q=O/'city_2000_difference.json';q.write_text(json.dumps({'different_ids':differences,'count':len(differences),'max_abs_delta_Su':max(abs(p['Su']-q['Su']) for p,q in zip(short['off'],short['on'])),'off_sha256':sha(O/'city_2000_off_points80.json'),'on_sha256':sha(O/'city_2000_on_points80.json'),'passed':bool(differences)},indent=2)+'\n');ready(q)
 if not differences:raise RuntimeError('city activation short-run fields identical')
 verdict['stage']='B_passed';q=O/'stage_B_verdict.json';q.write_text(json.dumps(verdict,indent=2)+'\n');ready(q)
 ack=O/'host_ack.json'; expected={p.name[:-7]:p.read_text().strip() for p in O.glob('*.sha256')}
 while not ack.exists():
  budget_guard(0,'final host ACK');time.sleep(2)
 assert json.loads(ack.read_text())==expected,'ACK mismatch'
 (O/'run.done').write_text('A and B gates passed; all evidence ready\n');ready(O/'run.done')
if __name__=='__main__':
 try:main()
 except BaseException:
  O.mkdir(parents=True,exist_ok=True);p=O/'run.failed';p.write_text(traceback.format_exc());ready(p);raise

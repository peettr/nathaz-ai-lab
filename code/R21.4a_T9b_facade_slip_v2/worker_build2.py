#!/usr/bin/env python3
"""T9b-build2 remote worker; ordered gates, exclusive outputs, no Case E ON production."""
import pathlib,os,time,sys,tarfile,hashlib,json,subprocess,shutil,traceback,io
import numpy as np
from remote_worker_run2 import vtk_map
from t5_reference_worker import sampled
R=pathlib.Path('/content'); W=R/'t9b2'; O=W/'out'; S=W/'stage'; C=W/'cases'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1<<20),b''):h.update(x)
 return h.hexdigest()
def marker(p):
 (p.with_name(p.name+'.sha256')).write_text(sha(p)+'\n')
 print('READY',p.name,sha(p),flush=True)
def cmd(args,cwd,env=None,timeout=1200,tag='job'):
 with (O/(tag+'.log')).open('x') as f:
  p=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 print('EXIT',tag,p.returncode,flush=True)
 marker(O/(tag+'.log'))
 if p.returncode:raise RuntimeError(tag+' failed '+str(p.returncode))
def main():
 W.mkdir(exist_ok=False);O.mkdir()
 archive=R/'t9b2_stage.tar.gz'; meta=json.loads((R/'t9b2_archive.json').read_text())
 assert sha(archive)==meta['archive_sha256']
 with tarfile.open(archive) as t:
  for m in t.getmembers():
   assert (m.name=='stage' or m.name.startswith('stage/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()),m.name
  t.extractall(W,filter='data')
 for name,h in meta['members'].items():assert sha(S/name)==h,name
 src=S/'FluidX3D_facade_v3'; case=S/'case'; ref=json.loads((S/'B2u_reference_points.json').read_text())
 for label,macro in [('on_cube','#define FACADE_CUBE_GATE'),('on_city',''),('off_city','')]:
  d=W/label;shutil.copytree(src,d)
  defines=d/'src/defines.hpp';v=defines.read_text()
  assert v.count('//#define FACADE_FREE_SLIP // T9b-build default OFF')==1
  if label.startswith('on_'):v=v.replace('//#define FACADE_FREE_SLIP // T9b-build default OFF','#define FACADE_FREE_SLIP // T9b-build ON')
  if macro:v=v.replace('#define FACADE_FREE_SLIP // T9b-build ON','#define FACADE_FREE_SLIP // T9b-build ON\n'+macro)
  defines.write_text(v)
  cmd(['make','Linux','-j8'],d,tag=label+'_build',timeout=1200)
  # CL capture comes from kernel constructor, not a host-generated approximation.
  env={**os.environ,'LD_LIBRARY_PATH':str(d/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  binary=d/'bin/FluidX3D'
  if label=='on_cube':
   env['LUW_CAPTURE_CL']=str(O/'on_cube_actual_opencl.cl')
   cmd([str(binary)],d,env,tag='cube_solver',timeout=500)
   marker(O/'on_cube_actual_opencl.cl')
   raw=R/'facade_cube_trace.csv'; assert raw.is_file();shutil.copyfile(raw,O/'cube_trace.csv');marker(O/'cube_trace.csv')
   import csv
   rows=list(csv.DictReader((O/'cube_trace.csv').open()));assert len(rows)==101
   drifts=[abs(float(x['relative_drift'])) for x in rows]
   faces=[int(x['wall_faces']) for x in rows]
   tangents=[float(x['wall_tangential_speed_mean']) for x in rows]
   # Cell-centre flux is a diagnostic, NOT automatically the zero wall-face flux.
   metrics={'max_relative_mass_drift':max(drifts),'min_wall_faces':min(faces),'min_tangential_speed':min(tangents),'max_abs_cell_center_normal_flux_sum':max(abs(float(x['wall_normal_cell_flux_sum'])) for x in rows)}
   (O/'cube_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n');marker(O/'cube_metrics.json')
   if max(drifts)>1.e-6 or min(faces)==0 or min(tangents)<=0:raise RuntimeError('gate2 mass/tangential fail')
  else:
   dest=C/label;shutil.copytree(case,dest)
   env['LUW_CAPTURE_CL']=str(O/(label+'_actual_opencl.cl'))
   env['LUW_EXPORT_FLAGS']=str(dest/'native_flags.bin')
   if label=='on_city':env['LUW_FLAGS_ONLY']='1'
   # off_city runs full unchanged baseline; output additional raw flags before solve.
   cmd([str(binary),str(dest/'conf.luwpf')],dest,env,tag=label+'_solver',timeout=4200 if label=='off_city' else 700)
   flags=dest/'native_flags.bin'; assert flags.stat().st_size==500*500*270
   raw=np.memmap(flags,dtype=np.uint8,mode='r',shape=(270,500,500))
   np.savez_compressed(O/(label+'_flags.npz'),flags=raw)
   marker(O/(label+'_flags.npz'))
   if label=='off_city':
    vtk=list((dest/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,vtk
    v=vtk_map(vtk[0]);assert v['dims']==(500,500,270) and v['origin']==(0.,0.,-20.)
    rows=[{'id':int(p['id']),'obs':float(p['after']),**sampled(v,p)} for p in ref['rows']]
    assert len(rows)==80 and {p['id'] for p in rows}==set(range(1,81))
    p=O/'points80.json';p.write_text(json.dumps({'label':'E_s101_off','uref':ref['uref'],'rows':rows,'source_vtk_sha256':sha(vtk[0]),'sample_height_above_wall_m':2.0,'vtk_label_z_m':2.5},indent=2)+'\n');marker(p)
    target='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
    (O/'gate1.json').write_text(json.dumps({'observed_sha256':sha(p),'expected_sha256':target,'equal':sha(p)==target},indent=2)+'\n');marker(O/'gate1.json')
    if sha(p)!=target:raise RuntimeError('gate1 bitwise failure')
  marker(O/(label+'_actual_opencl.cl'))
  if label=='on_city':
   # The raw comparison is done on host after verified pull; do not run ON city.
   pass
 (O/'run.done').write_text('gate1 and gate2 preliminary passed; flag comparison pending host\n')
if __name__=='__main__':
 try:main()
 except BaseException:
  traceback.print_exc();O.mkdir(parents=True,exist_ok=True)
  (O/'run.failed').write_text(traceback.format_exc());raise

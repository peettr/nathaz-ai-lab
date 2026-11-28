#!/usr/bin/env python3
"""Colab-only four-case solver and compact sampled-field exporter."""
from pathlib import Path
import os,sys,time,json,hashlib,zipfile,subprocess,math,traceback
import numpy as np
ROOT=Path('/content/t3_stage'); OUT=Path('/content/t3_out')
MAN=None; DEADLINE=None; RATE=None
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def check_budget(case):
 # Reserve 8 min for extraction, transfer and stop; case estimate 2x prior B2u measured time.
 c=MAN['cases'][case]; ref=1730*(c['cells_total']/(500*500*470))*(c['steps']/31000)
 if time.time()+2*ref+480 > DEADLINE: raise RuntimeError(f'budget before {case}: insufficient time for conservative solver+teardown')
def vtk_map(path):
 with path.open('rb') as f:
  lines=[]
  for _ in range(25):
   t=f.readline().decode('ascii').strip();lines.append(t)
   if t.startswith('LOOKUP_TABLE'):break
  offset=f.tell()
 dims=tuple(map(int,next(s for s in lines if s.startswith('DIMENSIONS')).split()[1:]));nx,ny,nz=dims
 origin=tuple(map(float,next(s for s in lines if s.startswith('ORIGIN')).split()[1:])); spacing=tuple(map(float,next(s for s in lines if s.startswith('SPACING')).split()[1:])); n=nx*ny*nz; pos=offset
 raw=np.memmap(path,mode='r',dtype='u1');fields={}
 for name,components in [('u_avg',3),('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1)]:
  if name!='u_avg':
   with path.open('rb') as f:f.seek(pos);tag=f.readline().decode().strip();lookup=f.readline().decode().strip()
   assert tag==f'SCALARS {name} float {components}' and lookup=='LOOKUP_TABLE default',(name,tag,lookup)
   pos+=len(tag)+len(lookup)+2
  fields[name]=np.ndarray((nz,ny,nx,components) if components==3 else (nz,ny,nx),dtype='>f4',buffer=raw,offset=pos)
  pos+=4*n*components
 assert pos==path.stat().st_size,(pos,path.stat().st_size)
 return dict(dims=dims,origin=origin,spacing=spacing,fields=fields,header=lines)
def calc(case,base):
 c=MAN['cases'][case];dx=c['dx']; files=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(files)==1,files
 vtk=files[0];v=vtk_map(vtk);nx,ny,nz=v['dims'];ox,oy,oz=v['origin'];d=v['spacing'][0]
 assert abs(d-dx)<0.00001 and all(abs(s-dx)<0.00001 for s in v['spacing']),v['spacing']
 assert nx==round(500/dx) and ny==round(30/dx) and nz==round(270/dx),v['dims']
 f=v['fields']; ground_k=round((0-oz)/dx)
 # Independently determine numerical wall from the binary native fluid field at 3 open-ground sites.
 wall=[]
 for x,y in ((2.,15.),(252.,15.),(400.,15.)):
  i=round((x-ox)/dx);j=round((y-oy)/dx)
  a=np.asarray(f['fluid'][:min(nz,ground_k+12),j,i]);first=int(np.flatnonzero(a>.5)[0]);wall.append({'xy':[x,y],'first_index':first,'first_label_m':oz+first*dx,'wall_m':oz+(first-.5)*dx})
 assert max(w['wall_m'] for w in wall)-min(w['wall_m'] for w in wall)<1e-6
 zlabel=wall[0]['wall_m']+2.; kf=(zlabel-oz)/dx;k0=math.floor(kf);w=kf-k0
 assert 0<=k0<nz-1 and k0>=wall[0]['first_index']
 yindices=[j for j in range(ny) if 10-1e-7<=oy+j*dx<=20+1e-7]; assert len(yindices)>=15
 xs=[dx,2.,5.,10.,25.,50.,75.,100.,125.,150.,175.,200.,225.,MAN['xc_m'],275.,300.,325.,350.,375.,400.,425.,450.,475.]
 def row(x,z,members):
  i=round((x-ox)/dx);zidx=(z-oz)/dx;k=math.floor(zidx);a=zidx-k
  assert 0<=i<nx and 0<=k<nz-1
  vec0=np.asarray(f['u_avg'][k,members,i],dtype='f8');vec1=np.asarray(f['u_avg'][k+1,members,i],dtype='f8')
  ff0=np.asarray(f['fluid'][k,members,i]);ff1=np.asarray(f['fluid'][k+1,members,i]); assert np.all(ff0>.5) and np.all(ff1>.5),(x,z,'solid')
  u=(1-a)*vec0+a*vec1
  return float(np.linalg.norm(np.mean(u,axis=0)))  # mean vector across y, then norm; see alternate per-column below
 def pointwise_band(x,z,members):
  i=round((x-ox)/dx);kf=(z-oz)/dx;k=math.floor(kf);a=kf-k
  assert 0<=i<nx and 0<=k<nz-1
  assert np.all(f['fluid'][k,members,i]>.5) and np.all(f['fluid'][k+1,members,i]>.5)
  u=(1-a)*np.asarray(f['u_avg'][k,members,i],dtype='f8')+a*np.asarray(f['u_avg'][k+1,members,i],dtype='f8')
  return float(np.linalg.norm(u,axis=-1).mean())
 curve=[{'x_m':x,'G_mps':pointwise_band(x,zlabel,yindices)} for x in xs]
 xc=MAN['xc_m'];profile=[{'height_agl_m':round(h*.5,3),'G_mps':(pointwise_band(xc,wall[0]['wall_m']+h*.5,yindices) if h>0 else None),'note':('below first-fluid label; no fluid-only interpolation' if h==0 else '')} for h in range(0,41)]
 side=[]
 for x in (2.,xc,400.):
  side.append({'x_m':x,'columns':[{'y_m':y,'U2_mps':pointwise_band(x,zlabel,[round((y-oy)/dx)])} for y in MAN['side_profile_y_m']]})
 # Explicitly archive first-fluid and sub-ground native flag at all sampled sites.
 summary={'case':case,'config_sha256':digest(base/'conf.luwpf'),'source_setup_sha256':digest(ROOT/'FluidX3D/src/setup.cpp'),'vtk_sha256':digest(vtk),'vtk_bytes':vtk.stat().st_size,'vtk_header':v['header'],'dims':v['dims'],'origin':v['origin'],'spacing':v['spacing'],'wall_samples':wall,'label_for_true_2m_m':zlabel,'center_band_y_m':MAN['center_band_y_m'],'x_c_m':xc,'G_curve':curve,'vertical_at_xc':profile,'side_profiles':side,'inlet_G2_mps':curve[1]['G_mps'],'xc_G2_mps':next(i['G_mps'] for i in curve if i['x_m']==xc),'observable':'mean_y |time-mean vector u| at true 2 m; SI units from VTK'}
 assert all(q['G_mps'] is not None and np.isfinite(q['G_mps']) and q['G_mps']>0 for q in curve+profile[1:])
 return summary

def run():
 source=ROOT/'FluidX3D';build=OUT/'build.log'
 with build.open('w') as f:p=subprocess.run(['make','Linux','-j8'],cwd=source,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1500)
 assert p.returncode==0,('build failed',p.returncode)
 print('BUILD_OK',flush=True)
 binary=source/'bin/FluidX3D';assert binary.is_file()
 env={**os.environ,'LD_LIBRARY_PATH':str(source/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
 for case in ('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102'):
  check_budget(case)
  base=ROOT/case; conf=base/'conf.luwpf'; assert digest(conf)==MAN['cases'][case]['conf_sha256']
  print('START',case,'seconds_remaining',int(DEADLINE-time.time()),flush=True)
  t=time.time()
  with (OUT/f'{case}_solver.log').open('w') as f:p=subprocess.run([str(binary),str(conf)],cwd=base,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,timeout=max(60,DEADLINE-time.time()-360))
  (OUT/f'{case}_exit.json').write_text(json.dumps({'solver_exit':p.returncode,'elapsed_s':time.time()-t,'case':case})+'\n')
  print('SOLVER_EXIT',case,p.returncode,'elapsed_s',int(time.time()-t),flush=True)
  assert p.returncode==0,(case,p.returncode)
  summary=calc(case,base);(OUT/f'{case}_metrics.json').write_text(json.dumps(summary,indent=2)+'\n')
  files=[OUT/f'{case}_metrics.json',OUT/f'{case}_exit.json',OUT/f'{case}_solver.log',build,conf,base/'proj_temp/CaseE_PF.stl',ROOT/'FluidX3D/src/setup.cpp',ROOT/'FluidX3D/src/defines.hpp']
  manifest={f.name: {'sha256':digest(f),'size':f.stat().st_size} for f in files}; m=OUT/f'{case}_manifest.json';m.write_text(json.dumps(manifest,indent=2)+'\n')
  z=OUT/f'{case}.zip'
  with zipfile.ZipFile(z,'x',compression=zipfile.ZIP_DEFLATED) as archive:
   for f in files+[m]:archive.write(f,arcname=f.name)
  with zipfile.ZipFile(z) as archive: assert archive.testzip() is None
  (OUT/f'{case}.sha256').write_text(digest(z)+'\n')
  print('RESULT',case,digest(z),flush=True)
 (OUT/'run.done').write_text('complete\n');print('ALL_DONE',flush=True)
if __name__=='__main__':
 OUT.mkdir(exist_ok=True)
 MAN=json.loads((ROOT/'stage_manifest.json').read_text())
 DEADLINE=float(os.environ['T3_DEADLINE']); RATE=float(os.environ['T3_RATE'])
 try:run()
 except BaseException:
  traceback.print_exc();(OUT/'run.failed').write_text(traceback.format_exc());raise

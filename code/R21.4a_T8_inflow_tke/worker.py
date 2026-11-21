#!/usr/bin/env python3
"""T8 single-case GPU worker: frozen T5 input, extra read-only VTK extraction."""
import pathlib,json,hashlib,tarfile,subprocess,os,time,traceback,shutil,math
import numpy as np
from remote_worker_run2 import vtk_map
from t5_sampler import sampled
R=pathlib.Path('/content');S=R/'stage';O=R/'t8_out';LABEL='E_s101_off'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run():
 O.mkdir(exist_ok=False)
 archive=R/'stage_t5.tar.gz';assert sha(archive)==json.loads((R/'archive.json').read_text())['sha256']
 with tarfile.open(archive) as t:
  for m in t.getmembers():assert (m.name=='stage' or m.name.startswith('stage/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()),m.name
  assert not S.exists();t.extractall(R,filter='data')
 man=json.loads((S/'manifest.json').read_text());ref=json.loads((R/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80 and ref['uref']==3.9286416
 src=S/'FluidX3D_off'
 for n,h in man['source']['off'].items():assert sha(src/'src'/n)==h
 base=R/'t8_case';shutil.copytree(S/'cases'/LABEL,base)
 conf=base/'conf.luwpf';assert sha(conf)==man['cases'][LABEL]['config_sha256']
 assert 'output_tke_ti_tls = [tke]' in conf.read_text()
 deadline=float(os.environ['T8_DEADLINE'])
 if time.time()+1150>deadline:raise RuntimeError('budget insufficient before build')
 with (O/'build.log').open('x') as f:p=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=600,stdin=subprocess.DEVNULL)
 print('BUILD',p.returncode,flush=True)
 if p.returncode:raise RuntimeError('build failure')
 if time.time()+1050>deadline:raise RuntimeError('budget insufficient before solver')
 env={**os.environ,'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),'LUW_GROUND_MIX_A':'0','LUW_CAPTURE_CL':str(O/'actual_opencl.cl')}
 start=time.time()
 with (O/'solver.log').open('x') as f:p=subprocess.run([str(src/'bin/FluidX3D'),str(conf)],cwd=base,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=max(60,deadline-time.time()-300))
 (O/'exit.json').write_text(json.dumps({'solver_exit':p.returncode,'elapsed_s':time.time()-start})+'\n')
 print('SOLVER_EXIT',p.returncode,round(time.time()-start),flush=True)
 if p.returncode:raise RuntimeError('solver failed')
 vtk=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,vtk
 v=vtk_map(vtk[0]);assert v['dims']==(500,500,270) and v['origin']==(0.,0.,-20.) and v['spacing']==(1.,1.,1.)
 f=v['fields'];assert 'tke' in f
 # Full frozen points80 producer format, including source VTK SHA.
 rows=[{'id':int(p['id']),'obs':float(p['after']),**sampled(v,p)} for p in ref['rows']]
 assert len({p['id'] for p in rows})==80 and all(math.isfinite(p['Su_ratio']) for p in rows)
 (O/'points80.json').write_text(json.dumps({'label':LABEL,'uref':ref['uref'],'rows':rows,'source_vtk_sha256':sha(vtk[0]),'sample_height_above_wall_m':2.0,'vtk_label_z_m':2.5},indent=2)+'\n')
 (O/'points80.sha256').write_text(sha(O/'points80.json')+'\n')
 # Index k=20..81 inclusive has VTK z=0..61 m; wall=0.5 m, interpolated 60 m AGL at z=60.5.
 sl=np.s_[20:82,150:351,0:61]
 meta={'k_start':20,'k_end_exclusive':82,'x_start':0,'x_end_exclusive':61,'y_start':150,'y_end_exclusive':351,'dims':v['dims'],'origin':v['origin'],'spacing':v['spacing'],'numerical_wall_z_m':0.5,'vtk_sha256':sha(vtk[0]),'config_sha256':sha(conf),'source_setup_sha256':sha(src/'src/setup.cpp'),'averaging_steps':[20000,31000,40]}
 with (O/'upstream_slice.npz').open('xb') as q:np.savez_compressed(q,u_avg=np.asarray(f['u_avg'][sl],dtype='<f4'),speed_mean=np.asarray(f['speed_mean'][sl],dtype='<f4'),tke=np.asarray(f['tke'][sl],dtype='<f4'),fluid=np.asarray(f['fluid'][sl],dtype='u1'),metadata=json.dumps(meta))
 (O/'upstream_slice.sha256').write_text(sha(O/'upstream_slice.npz')+'\n')
 obs=json.loads((R/'comparison.json').read_text());out=[]
 for x in (5,45):
  for row in obs['rows']:
   z=float(row['z_m']);idx=(0.5+z+20)-20; k=math.floor(0.5+z+20);w=0.5+z+20-k
   assert 20<=k and k+1<82
   jj=np.arange(150,351)
   good=(f['fluid'][k,jj,x]>.5)&(f['fluid'][k+1,jj,x]>.5)
   assert good.sum()>0
   tke=((1-w)*np.asarray(f['tke'][k,jj,x],dtype='f8')+w*np.asarray(f['tke'][k+1,jj,x],dtype='f8'))[good]
   uu=((1-w)*np.asarray(f['u_avg'][k,jj,x,0],dtype='f8')+w*np.asarray(f['u_avg'][k+1,jj,x,0],dtype='f8'))[good]
   km=float(tke.mean());um=float(uu.mean());ko=float(row['k_obs_m2s2']);uo=float(row['U_obs_mps'])
   out.append({'x_m':x,'height_agl_m':z,'fluid_columns':int(good.sum()),'total_columns':len(jj),'k_model_m2s2':km,'k_obs_m2s2':ko,'kappa':km/ko,'U_model_streamwise_mps':um,'U_obs_mps':uo,'U_ratio':um/uo})
 (O/'profile.json').write_text(json.dumps({'source_observation_sha256':obs['source_sha256'],'profile':out,'window':'steps 20000..31000 stride40','method':'at each y, linear z interpolation of tke and streamwise u_x, then arithmetic mean over fluid-supported y=150..350 inclusive; U_obs and k_obs from frozen AF comparison.json'},indent=2)+'\n')
 for name in ('profile.json','solver.log','exit.json','actual_opencl.cl','build.log'):
  (O/(name+'.sha256')).write_text(sha(O/name)+'\n')
 print('READY',sha(O/'points80.json'),sha(O/'upstream_slice.npz'),flush=True)
 expected=sha(O/'points80.json')+' '+sha(O/'upstream_slice.npz')
 while not (O/'host.ack').exists():
  if time.time()+110>deadline:raise RuntimeError('host ACK deadline')
  time.sleep(5)
 assert (O/'host.ack').read_text().strip()==expected
 (O/'run.done').write_text('host verified\n');print('ALL_DONE',flush=True)
if __name__=='__main__':
 try:run()
 except BaseException:
  traceback.print_exc();O.mkdir(exist_ok=True);(O/'run.failed').write_text(traceback.format_exc());raise

"""AERO-ODE frozen west checkpoints, VM-only zero-shot forecast driver.
No HRRR/ERA5 read after ngcm.forward starts except evaluation truth AFTER forecast tensors
are fully materialized and checkpointed; source audit in report must inspect this file.
"""
import os,sys,hashlib,pathlib,json,time,argparse,traceback
os.environ['HDF5_USE_FILE_LOCKING']='FALSE';os.environ['XLA_PYTHON_CLIENT_MEM_FRACTION']='.30';os.environ['XLA_PYTHON_CLIENT_ALLOCATOR']='platform';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';os.environ['PYTORCH_CUDA_ALLOC_CONF']='expandable_segments:True'
import numpy as np,torch
P=pathlib.Path('/content/l264a100');ROOT=P/'AERO_ODE';T=P/'texas';ERA_ROOT=P/'fast_data/data/era5_test';HRRR_ROOT=P/'fast_data/data/hrrr_test';OUT=T/'predictions';OUT.mkdir(exist_ok=True)
CHECKS={'air':('AERO_AIR_WD/checkpoints_film_25/model_ep5.pth','5d735208a707b865f1eeba344f11a4ee004cc4ab52b93a75e83dd6e7920476bb'),'surface':('AERO_Surface_WD/checkpoints_film_v2/model_ep5.pth','4dccbfc7d4367e0e8d31379a3fe0b416ff4c5bdc6fc4790576bda5054355330c')}
NGCM=('shared_assets/NeuralGCM_Weights/neuralgcm_04_30_2024_neural_gcm_dynamic_forcing_deterministic_1_4_deg.pkl','43715bc86af9df6b1bb824c44e2ee61572c9f865d34ac6c7131fd4507984eeb7')

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def prepare(which,variant):
 sys.path.insert(0,str(ROOT/('AERO_AIR_WD' if which=='air' else 'AERO_Surface_WD')))
 import AERO_ODE_v3 as aero, AERO_ODE_Dataset_v3 as dataset, inference_components as ic
 if which=='air':
  if variant=='original':statroot=ROOT/'AERO_AIR_WD/Hrrr_rb'
  else:statroot=T/(variant+'_air')
  stat=ic.StaticDataManager(str(statroot),stat_dir=str(ROOT/'data/hrrr_stat'),device='cuda')
  model=ic.CorrectionModel(time_emb_dim=128,backbone='unet3plus').cuda()
  from test_film_wb import StrangSplittingIntegrator
  integrator=StrangSplittingIntegrator(dt=3600.)
 else:
  statroot=ROOT/'AERO_Surface_WD/Hrrr_rb/data' if variant=='original' else T/(variant+'_static')
  stat=ic.StaticDataManager(str(ROOT/'AERO_Surface_WD/Hrrr_rb/data'),device='cuda',target_levels=ic.TARGET_LEVELS,static_data_path=str(statroot))
  model=ic.DiagnosisModel(in_channels_dynamic=74,in_channels_static=14,out_channels=4,time_emb_dim=128,backbone='unet3plus').cuda();integrator=None
 ckpt=ROOT/CHECKS[which][0];assert sha(ckpt)==CHECKS[which][1]
 assert sha(ROOT/NGCM[0])==NGCM[1]
 state=torch.load(str(ckpt),map_location='cpu',weights_only=True)['model_state_dict'];model.load_state_dict({k.removeprefix('module.'):v for k,v in state.items()});model.eval()
 ngcm=aero.NeuralGCMInference(str(ROOT/NGCM[0]),inner_steps=1,outer_steps=73)
 coords=statroot if which=='surface' else statroot/'data'
 lat=np.load(coords/'hrrr_west_lat.npy').T;lon=np.load(coords/'hrrr_west_lon.npy').T
 return aero,dataset,ic,stat,model,integrator,ngcm,lat,lon

def initial_input(dataset,day):
 ds=dataset.ERA5XarrayDataset(str(ERA_ROOT),hrrr_root_dirs=[],predict_lead_time=73,filter_invalid_hrrr=False)
 target=f'2024-04-{day:02d} 00:00:00';ids=[i for i,entry in enumerate(ds.timeline) if str(entry['timestamp'])==target]
 assert len(ids)==1,(target,ids)
 initial=ds._read_era5_data(ids[0],1)
 assert all(np.asarray(v).shape[0]==1 for v in initial.values())
 dsx=ds._wrap_as_xarray(initial,ds.timeline[ids[0]]['timestamp'],1)
 return [dsx],[f'2024/04/{day:02d}/00']

def forecast(which,day,aero,dataset,ic,stat,model,integrator,ngcm,lat,lon):
 # The ONLY ERA5 read in this forecast is here, BEFORE ngcm.forward.
 init,times=initial_input(dataset,day)
 start=time.monotonic()
 with torch.inference_mode():
  pred,phy=ngcm.forward(init,target_levels=[300,500,700,850,925] if which=='air' else ic.TARGET_LEVELS,include_era5_label=False,region_lon=lon,region_lat=lat)
  pred[:,:5]/=9.8;phy[:,:5]/=9.8
  pred=pred.permute(0,4,1,2,3).to('cuda');phy=phy.permute(0,4,1,2,3).to('cuda')
  B,T,C,W,H=phy.shape;assert (B,T,W,H)==(1,73,408,440),(B,T,C,W,H)
  if which=='air':
   mean=torch.zeros(1,1,35,1,1,device='cuda');std=torch.ones_like(mean)
   mean[0,0,:25]=stat.mean[:25].view(25,1,1);std[0,0,:25]=stat.std[:25].view(25,1,1)
   std[0,0,25:30]=7.538e-06;std[0,0,30:35]=1.979e-05
   dyn_in=torch.cat([(phy-mean)/(std+1e-9),(pred-phy)/(std+1e-9)],dim=2)
   chunk=4
  else:
   dyn_in=torch.cat([(phy-stat.input_mean)/(stat.input_std+1e-9),(pred-phy)/(stat.input_std+1e-9),ic.compute_solar_features(times,T,lat,lon,'cuda')],dim=2)
   chunk=8
  static=stat.get_static_input(B);steps,hours,months=ic.compute_time_indices(times,T,'cuda')
  pieces=[]
  for t0 in range(0,T,chunk):
   t1=min(t0+chunk,T);tc=t1-t0
   x=dyn_in[:,t0:t1].reshape(tc,dyn_in.shape[2],W,H)
   s=static.unsqueeze(1).expand(-1,tc,-1,-1,-1).reshape(tc,static.shape[1],W,H)
   y=model(x,s,steps[t0:t1],hours[t0:t1],months[t0:t1])
   if which=='air':
    inc=y*(stat.target_std+1e-9);post=phy[:,t0:t1,:25].reshape(tc,25,W,H)
    pre=post if t0==0 else phy[:,t0-1:t1-1,:25].reshape(tc,25,W,H)
    y=integrator.step(pre,post,inc)
   else:y=y*(stat.surface_std+1e-9)+stat.surface_mean
   pieces.append(y.reshape(tc,-1,W,H).cpu().numpy())
  output=np.concatenate(pieces,axis=0).transpose(0,1,3,2).copy()
  # NeuralGCM standard prediction is pred; phy is its physics-only diagnostic.
  base=pred[0,:,:25] if which=='air' else None
  if base is not None:base=base.cpu().numpy().transpose(0,1,3,2).copy()
  assert np.isfinite(output).all() and (base is None or np.isfinite(base).all())
 seconds=time.monotonic()-start
 return output,base,seconds

def run(which,region,variant,days):
 assert (T/'build_static.done').is_file()
 manifest=json.loads((P/'fast_data/fast_increment.json').read_text())
 completed={row['path'] for row in manifest}
 for day in days:
  assert f'data/era5_test/2024/04/{day:02d}/202404{day:02d}.nc' in completed, f'ERA5 day {day} not fully staged'
  if region=='west':assert f'data/hrrr_test/04/{day:02d}.h5' in completed, f'HRRR west day {day} not fully staged'
 aero,dataset,ic,stat,model,integ,ngcm,lat,lon=prepare(which,variant)
 for day in days:
  key=f'{region}_{variant}_{which}_{day:02d}'
  dst=OUT/(key+'.npz')
  if dst.exists():
   with np.load(dst,allow_pickle=False) as z:assert z['pred'].shape[0]==73 and np.isfinite(z['pred']).all()
   print('SKIP_EXISTING',key,flush=True);continue
  pred,base,sec=forecast(which,day,aero,dataset,ic,stat,model,integ,ngcm,lat,lon)
  # All model inputs and GPU tensors have been materialized to numpy BEFORE any HRRR verification read.
  # West matched-reference data are only used here for evaluation, and never passed back to forecast().
  if region=='west':
   ds=dataset.ERA5XarrayDataset(str(ERA_ROOT),hrrr_root_dirs=[str(HRRR_ROOT)],predict_lead_time=73)
   global_idx=next(i for i,e in enumerate(ds.timeline) if str(e['timestamp'])==f'2024-04-{day:02d} 00:00:00')
   truth=ds._read_hrrr_data(global_idx,73)[:,0:25 if which=='air' else 39]
   truth=truth[:,0:25] if which=='air' else truth[:,35:39]
   assert truth.shape==pred.shape,(truth.shape,pred.shape)
   # Persist only SSE summaries, not author arrays.
   n=pred.shape[2]*pred.shape[3];sse=((pred[1:]-truth[1:])**2).sum(axis=(0,2,3),dtype=np.float64)
   payload={'sse':sse,'count':np.int64(n*72),'seconds':np.float64(sec)}
  else:
   # Pressure-level comparison needs Z/T only; preserve full-precision values.
   scored=pred[:,:10] if which=='air' else pred
   payload={'pred':scored.astype(np.float32),'seconds':np.float64(sec)}
   if base is not None:payload['baseline_ngcm']=base[:,:10].astype(np.float32)
  with dst.open('xb') as f:
   # AIR Texas: uncompressed float32 accelerates bounded VM-only I/O; values identical.
   (np.savez if region=='texas' and which=='air' else np.savez_compressed)(f,**payload)
  print('FORECAST_DONE',key,'seconds',round(sec,3),'shape',pred.shape,'bytes',dst.stat().st_size,flush=True)
  with (T/'forecast_increment.jsonl').open('a') as f:f.write(json.dumps({'key':key,'seconds':sec,'bytes':dst.stat().st_size})+'\n')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--net',choices=['air','surface'],required=True);ap.add_argument('--region',choices=['west','texas'],required=True);ap.add_argument('--variant',choices=['original','west','texas'],required=True);ap.add_argument('--days',nargs='+',type=int,required=True);a=ap.parse_args()
 run(a.net,a.region,a.variant,a.days)

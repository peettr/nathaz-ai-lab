"""VM-only programmatic evaluation of 10 TX forecasts and WD static intervention."""
import pathlib,json,datetime,math
import numpy as np
P=pathlib.Path('/content/l264a100/texas');F=P/'predictions';A=P/'analysis'
KEYS=['mslp','u10','v10','t2m'];LEADS=[1,6,12,24,36,48,60,72]

def wests():
 names=['Z300','Z500','Z700','Z850','Z925','T300','T500','T700','T850','T925','MSLP','U10','V10','T2m']
 vals={}
 for variant in ('original','west'):
  sums=[];counts=[]
  for net in ('air','surface'):
   chunks=[np.load(F/f'west_{variant}_{net}_{day:02d}.npz',allow_pickle=False) for day in (1,2,3)]
   sse=sum((c['sse'] for c in chunks));count=sum(int(c['count']) for c in chunks)
   sums.extend(sse.tolist());counts.extend([count]*len(sse))
  # AIR layout Z,T,Q,U,V at 5 levels; 4 surface channels.
  chosen=list(range(0,5))+list(range(5,10))+list(range(25,29))
  vals[variant]=[math.sqrt(sums[i]/counts[i]) for i in chosen]
 rows=[]
 for name,o,r in zip(names,vals['original'],vals['west']):rows.append({'variable':name,'original_rmse':o,'reconstructed_rmse':r,'relative_difference':abs(r-o)/o})
 result={'n':3,'dates':['2024-04-01','2024-04-02','2024-04-03'],'relative_difference_formula':'abs(RMSE_rebuilt-RMSE_original)/RMSE_original','rows':rows}
 (P/'west_intervention.json').write_text(json.dumps(result,indent=2));return result

def texas():
 # Model forecast has shape (73,4,440,408) in NOAA scan axes, leads 1..72 scored.
 meta=json.loads((P/'window.json').read_text());wy,wx=meta['west_offset'];ty,tx=meta['texas_offset'];H,W=meta['shape']
 yy,xx=np.ogrid[ty:ty+H,tx:tx+W]; overlap=(yy>=wy)&(yy<wy+H)&(xx>=wx)&(xx<wx+W)
 masks={'strict':~overlap,'overlap':overlap};counts={k:int(v.sum()) for k,v in masks.items()}
 assert counts['strict']+counts['overlap']==H*W and counts['strict']>0
 # Full April f00, on exactly this window, irrespective of which forecasts are scored.
 monthly=[]
 for i in range(720):
  stamp=datetime.datetime(2024,4,1)+datetime.timedelta(hours=i)
  with np.load(A/f'{stamp:%Y%m%d%H}.npz',allow_pickle=False) as z:
   monthly.append(np.hypot(z['u10'],z['v10']).astype(np.float32).reshape(-1))
 arr=np.concatenate(monthly);assert np.isfinite(arr).all() and len(arr)==720*H*W
 p95=float(np.quantile(arr,.95));del arr,monthly
 variants=['aero','persistence'];metric_vars=KEYS+['speed']
 def top_indices(values,k):
  threshold=np.partition(values,-k)[-k]
  high=np.flatnonzero(values>threshold)
  tied=np.flatnonzero(values==threshold)[:k-len(high)]
  return np.concatenate((high,tied))
 sums={region:{method:np.zeros((5,72),dtype=np.float64) for method in variants} for region in masks}
 n={region:np.zeros(72,dtype=np.int64) for region in masks}
 strong={region:{method:{'sse':0.,'bias':0.,'n':0} for method in variants} for region in masks}
 ranked={region:{'truth':[],'aero':[],'persistence':[]} for region in masks}
 for day in range(1,11):
  ds=datetime.datetime(2024,4,day)
  with np.load(F/f'texas_texas_surface_{day:02d}.npz',allow_pickle=False) as z:
   pred=np.asarray(z['pred'],dtype=np.float32)
  assert pred.shape==(73,4,H,W)
  truth=np.empty_like(pred)
  for hour in range(73):
   stamp=ds+datetime.timedelta(hours=hour)
   with np.load(A/f'{stamp:%Y%m%d%H}.npz',allow_pickle=False) as z:
    for iv,k in enumerate(KEYS):truth[hour,iv]=z[k]
  pers=np.broadcast_to(truth[0:1],truth.shape)
  for region,mask in masks.items():
   for j in range(1,73):
    obs=truth[j,:,mask].T
    n[region][j-1]+=obs.shape[-1]
    ospeed=np.hypot(obs[1],obs[2]);high=ospeed>=p95
    ranked[region]['truth'].append(ospeed.astype(np.float32))
    # NeuralGCM outputs pressure-level channels only; no surface baseline exists.
    for method,output in [('aero',pred),('persistence',pers)]:
     q=output[j,:,mask].T
     pspeed=np.hypot(q[1],q[2]);diff=np.concatenate([q-obs,(pspeed-ospeed)[None]],axis=0)
     sums[region][method][:,j-1]+=np.square(diff,dtype=np.float64).sum(axis=1)
     wind=strong[region][method];wind['sse']+=np.square(pspeed[high]-ospeed[high],dtype=np.float64).sum();wind['bias']+=(pspeed[high]-ospeed[high]).sum(dtype=np.float64);wind['n']+=int(high.sum())
     ranked[region][method].append(pspeed.astype(np.float32))
  print('METRIC_DAY',day,'p95',p95,flush=True)
 report={'source':'NOAA noaa-hrrr-bdp-pds HRRR 2024-04 f00 analysis; author AERO-ODE 99516ae9cf + HF weight','p95_full_april_mps':p95,'p95_population':720*H*W,'groups':{}}
 for region in masks:
  block={'grid_cells':counts[region],'count_per_lead':n[region].tolist(),'rmse':{},'strong':{},'topk':{}}
  true=np.concatenate(ranked[region]['truth']);K=max(1,int(np.ceil(.01*len(true))))
  # Ties at the cutoff are resolved by earlier flattened (day, lead, y, x) index.
  truth_idx=top_indices(true,K);truth_mask=np.zeros(len(true),dtype=bool);truth_mask[truth_idx]=True
  for method in variants:
   block['rmse'][method]={name:np.sqrt(sums[region][method][i]/n[region]).tolist() for i,name in enumerate(metric_vars)}
   s=strong[region][method];block['strong'][method]={'n':s['n'],'speed_rmse':math.sqrt(s['sse']/s['n']) if s['n'] else None,'speed_bias':s['bias']/s['n'] if s['n'] else None}
   z=np.concatenate(ranked[region][method]);top=top_indices(z,K)
   block['topk'][method]={'k':K,'capture_rate':float(truth_mask[top].sum()/K),'n_scored':int(len(true))}
  report['groups'][region]=block
 (P/'texas_metrics.json').write_text(json.dumps(report,indent=2));print('METRICS_DONE',p95,{k:v['grid_cells'] for k,v in report['groups'].items()},flush=True)
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(12,4),sharey=True)
 for ax,(group,block) in zip(axes,report['groups'].items()):
  for method in variants:ax.plot(range(1,73),block['rmse'][method]['speed'],label=method)
  ax.set_title(group);ax.set_xlabel('Lead (h)');ax.set_ylabel('10 m speed RMSE (m/s)');ax.grid(alpha=.2);ax.legend()
 fig.suptitle('Source: NOAA HRRR f00 analysis, AERO-ODE HF weights, NeuralGCM')
 fig.tight_layout();fig.savefig(P/'texas_speed_rmse.png',dpi=140);plt.close(fig)
 (P/'surface_metrics.done').write_text('ok\n')
if __name__=='__main__':
 wests();texas()

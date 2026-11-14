"""Same-grid paired forecasts; never use aggregate truth RMSE as pairwise distance."""
import pathlib,json,numpy as np
P=pathlib.Path('/content/l264ctrl05');F=P/'texas/predictions';h,w=440,408
out={'source':'AERO-ODE HF 99516ae9cf weights and ERA5 2024-04-01 00Z; static NOAA HRRR f00 HGT/VGTYP 2024-04-01 plus Table 4','definition':'sqrt(mean((original west prediction at x+d - shifted prediction at x)^2)) on same HRRR grid cells','lead_hours':[1,24,72],'metrics':{},'shared_cells':{}}
def dist(a,b):
 z=a.astype(np.float64)-b.astype(np.float64)
 return {'rmse':float(np.sqrt(np.mean(z*z))),'bias':float(z.mean()),'p95_abs':float(np.quantile(abs(z),.95))}
for net,fields in [('surface',{'T2m':3,'U10':1}),('air',{'Z925':4})]:
 with np.load(F/f'shift_original_{net}_01.npz',allow_pickle=False) as z:ref=z['pred']
 for d in (0,10,50,150):
  with np.load(F/f'shift_shift{d}_{net}_01.npz',allow_pickle=False) as z:moved=z['pred']
  assert ref.shape==moved.shape and ref.shape[-2:]==(h,w),(ref.shape,moved.shape)
  out['shared_cells'][str(d)]=h*(w-d)
  for name,c in fields.items():
   out['metrics'].setdefault(name,{})[str(d)]={str(lead):dist(ref[lead,c,:,d:],moved[lead,c,:,:w-d]) for lead in (1,24,72)}
  del moved
 del ref
with (P/'ctrl_metrics.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out),flush=True)

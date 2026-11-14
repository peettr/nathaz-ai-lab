import pathlib,json,numpy as np
P=pathlib.Path('/content/l264ctrl05');F=P/'texas/predictions'; h,w=440,408
with np.load(F/'shift_original_air_01.npz',allow_pickle=False) as z:a=z['pred'][:,4]
out={'variable':'Z925','source':'AERO-ODE HF weights/ERA5 2024-04-01; NOAA HRRR f00 HGT/VGTYP','definition':'same-grid original minus shifted prediction RMSE','rows':[]}
for d in (0,10,50,150):
 with np.load(F/f'shift_shift{d}_air_01.npz',allow_pickle=False) as z:b=z['pred'][:,4]
 for lead in (1,24,72):
  delta=a[lead,:,d:].astype(np.float64)-b[lead,:,:w-d].astype(np.float64)
  out['rows'].append({'shift':d,'lead':lead,'cells':h*(w-d),'rmse':float(np.sqrt(np.mean(delta**2))),'bias':float(delta.mean())})
with (P/'air_ctrl_partial.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out),flush=True)

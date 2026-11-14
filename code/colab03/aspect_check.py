"""VM-only directional check against frozen author's western static file."""
import json, pathlib
import numpy as np
from scipy.ndimage import uniform_filter
p=pathlib.Path('/content/l264a100'); t=p/'texas'; r=p/'AERO_ODE/AERO_Surface_WD/Hrrr_rb/data'
y,x=np.load(t/'west_offsets.npy'); h,w=np.load(r/'hrrr_west_lat.npy').shape
z=np.load(t/'HGT.npy')[y:y+h,x:x+w].astype(np.float64)
dy,dx=np.gradient(z,3000.,3000.)
mag=np.maximum(np.hypot(dx,dy),1e-12)
# HRRR scan y increases to geographic north; author's sine follows westward downslope,
# while author's cosine follows northward upslope in delivered static files.
features={'aspect_sin':-dx/mag,'aspect_cos':dy/mag}
res={}
for name,v in features.items():
 a=np.load(r/(name+'.npy')).astype(np.float64)
 res[name]={'corr':float(np.corrcoef(v.ravel(),a.ravel())[0,1]),'max_abs_diff':float(np.max(abs(v-a))),'source_range':[float(v.min()),float(v.max())],'author_range':[float(a.min()),float(a.max())]}
print(json.dumps(res,indent=2),flush=True)
(t/'aspect_comparison_corrected.json').write_text(json.dumps(res,indent=2))

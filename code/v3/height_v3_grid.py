"""Correct representative-point sampling bias: use each matched building-ID's solid voxels."""
import json,time
from pathlib import Path
import numpy as np,pandas as pd
P=Path('/content/l2613v3');r=pd.read_csv(P/'height_matches_v3_fixed.csv');D={'start':time.time(),'method':'median occupied-column top over the mutually matched voxel building ID; only IDs with solid columns counted','matched':len(r)}
for step in (1.,.5):
 a=np.load(P/f'PLATEAU_{step:g}.npy',mmap_mode='r');ids=np.load(P/f'PLATEAU_{step:g}_ids.npy',mmap_mode='r').astype('int32');solid=(a==-3)
 occupied=solid.any(axis=2);top=np.where(occupied,(solid.shape[2]-1-np.argmax(solid[:,:,::-1],axis=2))*step,0)
 # Flatten once: one group per original building ID, with positive occupied columns only.
 df=pd.DataFrame({'id':ids[occupied].ravel(),'top':top[occupied].ravel()});heights=df.groupby('id')['top'].median().to_dict()
 r[f'voxel_id_{step:g}m']=[float(heights.get(int(k),0)) for k in r.voxel_id];r[f'absdiff_id_{step:g}m']=(r[f'voxel_id_{step:g}m']-r.measuredHeight_m).abs();r[f'reldiff_id_{step:g}m']=r[f'absdiff_id_{step:g}m']/r.measuredHeight_m
 D[f'{step:g}m']={'median_absdiff_m':float(r[f'absdiff_id_{step:g}m'].median()),'median_relative_diff':float(r[f'reldiff_id_{step:g}m'].median()),'within_1m':int((r[f'absdiff_id_{step:g}m']<=step).sum()),'within_10pct':int((r[f'reldiff_id_{step:g}m']<=.10).sum()),'unrepresented_ids':int((r[f'voxel_id_{step:g}m']==0).sum()),'max_absdiff_m':float(r[f'absdiff_id_{step:g}m'].max())}
r.to_csv(P/'height_matches_v3_id.csv',index=False);D['end']=time.time();(P/'height_v3_id.json').write_text(json.dumps(D,indent=2));(P/'height_v3_id.done').write_text('done');print(D,flush=True)

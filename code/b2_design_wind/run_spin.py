#!/usr/bin/env python3
"""Optional SPIN diagnostic: derive Pc/RMW from RAFT regression; not a gate input."""
import argparse, csv, json, pathlib, sys, time, zipfile
import numpy as np
sys.path.insert(0,'/content/b2')
import run_catalog_v3 as chain
ROOT=pathlib.Path('/content/b2')
def main():
 p=argparse.ArgumentParser();p.add_argument('--limit-files',type=int,default=0);a=p.parse_args()
 out=ROOT/('spin_pilot' if a.limit_files else 'spin_results_v4');out.mkdir(exist_ok=True)
 archive=zipfile.ZipFile(ROOT/'SPIN_v1.0.1_output.zip')
 names=sorted(x for x in archive.namelist() if x.startswith('SPIN_v1.0.1_output/SPIN_output/') and x.endswith('_with_vmax.txt'))
 assert len(names)==5570,len(names)
 if a.limit_files:names=names[:a.limit_files]
 summary=dict(files=len(names),storm_raw=0,selected=0,malformed=0,far=0,failed=0);ident=[];year=[];peaks=[];ratio=[];err=[];t0=time.time();uid=0
 def flush(batch):
  if not ident:return
  target=out/f'spin_{batch:05d}.npz';assert not target.exists()
  np.savez_compressed(target,ids=np.asarray(ident),years=np.asarray(year),peaks=np.asarray(peaks,dtype='float32'),ratios=np.asarray(ratio,dtype='float32'))
  ident.clear();year.clear();peaks.clear();ratio.clear()
 for fid,name in enumerate(names):
  lines=archive.read(name).decode().splitlines();heads=[i for i,l in enumerate(lines) if l.startswith('start')]
  for h,end in zip(heads,heads[1:]+[len(lines)]):
   uid+=1;summary['storm_raw']+=1
   try:
    expected=int(lines[h].split()[1]);rows=np.array([np.fromstring(line,sep=' ') for line in lines[h+1:end]])
    if len(rows)!=expected or rows.ndim!=2 or rows.shape[1]!=11 or expected<2 or not np.isfinite(rows[:,[2,3,10]]).all():summary['malformed']+=1;continue
    lat=rows[:,3];lon=(rows[:,2]+180)%360-180
    if not chain.near(lat,lon):summary['far']+=1;continue
    vmax=rows[:,10];kt=vmax/0.514444
    pc=1030.222-0.730*kt
    rmw=48.7*np.exp(0.0163637*lat-0.01450866*kt)
    ds=chain.make_track(lat,lon,pc,rmw,vmax,6,'spin')
    pred=chain.predict(ds)
    ident.append(uid);year.append(fid);peaks.append(np.stack([x[0] for x in pred]));ratio.append(np.stack([x[1] for x in pred]));summary['selected']+=1
    if len(ident)>=500:flush(fid)
   except Exception as exc:
    summary['failed']+=1
    if len(err)<20:err.append([name,int(h),repr(exc)])
  if (fid+1)%100==0:print('PROGRESS',fid+1,'/',len(names),summary,'wall',round(time.time()-t0,1),flush=True)
 flush(len(names));meta={'counts':summary,'errors':err,'wall_seconds':time.time()-t0,'sample_file_years':len(names),'path_dependence':'10 FAST realizations share each NeuralGCM path'}
 target=out/('pilot.json' if a.limit_files else 'complete.json');assert not target.exists();target.write_text(json.dumps(meta,indent=2));print('SPIN_DONE',meta,flush=True)
if __name__=='__main__':main()

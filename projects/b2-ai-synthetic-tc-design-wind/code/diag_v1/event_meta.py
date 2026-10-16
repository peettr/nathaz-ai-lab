"""Attach max-track vmax for every sampled synthetic event (no standards)."""
import csv,zipfile,pathlib,numpy as np,xarray as xr
P=pathlib.Path('/content');inp=P/'diag5/paired_peaks.csv'
ids={'RAFT':set(),'STORM':set()}
for r in csv.DictReader(open(inp)):ids[r['catalog']].add(int(r['event']))
rows=[];d=xr.open_dataset(P/'RAFT.NA.v20231016.nc')
for i in sorted(ids['RAFT']):
 v=d['vmax'][i].values;rows.append(('RAFT',i,float(np.nanmax(v))))
d.close()
with zipfile.ZipFile(P/'STORMV4.zip') as z:
 paths=sorted((a for a in z.namelist() if '_NA_' in a),key=lambda a:int(a.rsplit('_',1)[-1].split('.')[0]))
 for file_id,name in enumerate(paths):
  with z.open(name) as f:a=np.loadtxt(f,delimiter=',',dtype=float)
  key=a[:,0].astype('int64')*100+a[:,2].astype('int64');starts=np.r_[0,1+np.where(np.diff(key)!=0)[0]];ends=np.r_[starts[1:],len(a)]
  for b,e in zip(starts,ends):
   c=a[b:e];i=file_id*1000000+int(c[0,0])*100+int(c[0,2])
   if i in ids['STORM']:rows.append(('STORM',i,float(np.nanmax(c[:,8]*1.11/0.514444))))
with open(P/'diag5_event_meta.csv','w') as f:
 w=csv.writer(f);w.writerow(['catalog','event','max_vmax_kt']);w.writerows(rows)
assert len(rows)==sum(len(x) for x in ids.values()),(len(rows),[len(x) for x in ids.values()])
print('EVENT META',len(rows),sum(r[2]>=114 for r in rows),flush=True)

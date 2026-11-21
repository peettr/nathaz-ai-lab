#!/usr/bin/env python3.10
"""Read-only small-file resampling at the frozen T5 worker.py coordinates."""
import csv, hashlib, json, math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent; LOG=R.parent
W=LOG/'R21.4a_T7_buffer40_try2/widths.csv'
width={int(x['id']):x for x in csv.DictReader(W.open())}
wide={i for i in range(1,81) if width[i]['width_min_m'] and float(width[i]['width_min_m'])>=15}
assert len(wide)==64
cases=[('T5_off_s101','R21.4a_T5_caseE_WM_retry1','E_s101_off'),('T5_off_s102','R21.4a_T5_caseE_WM_retry2','E_s102_off'),('T5_on_s101','R21.4a_T5_caseE_WM_retry1','E_s101_on'),('T5_on_s102','R21.4a_T5_caseE_WM','E_s102_on'),('T6_on_s101','R21.4a_T6_z0_inlet','E_s101_on'),('T6_on_s102','R21.4a_T6_z0_inlet','E_s102_on')]
U=3.9286416
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def compute(case, folder, label):
 e=LOG/folder/'evidence'; thin=e/(label+'_thin.npz'); old=e/(label+'_points80.json'); assert thin.is_file() and old.is_file(),(thin,old)
 p=json.loads(old.read_text()); assert p['uref']==U and len(p['rows'])==80
 with np.load(thin) as d:
  md=json.loads(str(d['metadata'])); assert md['dims']==[500,500,270] and md['origin']==[0.,0.,-20.] and md['k_start']==20
  u=d['u_avg']; speed=d['speed_mean']; fluid=d['fluid']; assert u.shape==(27,500,500,3) and speed.shape==fluid.shape==(27,500,500)
  rows=[]
  for x in p['rows']:
   xyz=x['xyz_m']; q=[xyz[0],xyz[1],xyz[2]+20-md['k_start']]; ix=[math.floor(t) for t in q]; f=[t-i for t,i in zip(q,ix)]; vec=np.zeros(3); scalar=0.;solid=0.;nf=0
   for dz in (0,1):
    for dy in (0,1):
     for dx in (0,1):
      k,j,i=ix[2]+dz,ix[1]+dy,ix[0]+dx
      wt=(f[0] if dx else 1-f[0])*(f[1] if dy else 1-f[1])*(f[2] if dz else 1-f[2])
      vec+=wt*u[k,j,i,:];scalar+=wt*float(speed[k,j,i]);isfluid=float(fluid[k,j,i])>.5; nf+=int(isfluid);solid+=wt*(not isfluid)
   assert nf==x['fluid_corners'] and abs(solid-x['solid_weight'])<1e-8,(case,x['id'])
   assert abs(scalar-x['Su'])<2e-6,(case,x['id'],scalar,x['Su'])
   rows.append({'case':case,'id':x['id'],'group':'wide' if x['id'] in wide else 'narrow_near_16','obs':x['obs'],'xyz_m':xyz,'scalar':scalar/U,'vector3':float(np.linalg.norm(vec))/U,'horizontal2':float(np.linalg.norm(vec[:2]))/U,'fluid_corners':nf})
 return rows,{'thin_path':str(thin),'thin_sha256':sha(thin),'points80_source':str(old),'points80_sha256':sha(old),'vtk_sha256':md['vtk_sha256']}
allrows=[];provenance={}
for c,f,l in cases:
 rows,provenance[c]=compute(c,f,l);allrows+=rows
summary=[]
for c,_,_ in cases:
 for quantity in ('scalar','vector3','horizontal2'):
  rows=[r for r in allrows if r['case']==c]
  rr={'case':c,'quantity':quantity,'MAE_80':sum(abs(r[quantity]-r['obs']) for r in rows)/80}
  for name,subset in [('all80',rows),('wide64',[r for r in rows if r['group']=='wide']),('narrow_near16',[r for r in rows if r['group']!='wide'])]:
   rr['ratio_'+name]=sum(r[quantity] for r in subset)/sum(r['obs'] for r in subset)
  summary.append(rr)
for name,obj in [('summary.json',{'formula':'MAE=mean(|model-obs|); group total ratio=sum(model)/sum(obs), model normalized by Uref=3.9286416; sample trilinear fields first, then take vector norm','group_definition':'width_min_m >=15m wide64, complement narrow/near-wall16','sources':provenance,'rows':summary}),('points80_three_definitions.json',allrows)]:
 out=R/name;assert not out.exists();out.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,indent=2));print('point rows',len(allrows))

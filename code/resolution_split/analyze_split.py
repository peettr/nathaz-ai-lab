"""Post-process compact completed Colab outputs; no solver here."""
from pathlib import Path
import json,csv,math,statistics,hashlib
R=Path(__file__).resolve().parent;P=R.parent
paths={'E1':R/'E1_samples.json','E05':R/'E05_samples.json','C1G0':R/'C1G0_samples.json','C1':P/'resolution_crop_v2/C1v2_offset_samples.json','C05':P/'resolution_c05/C05_offset_samples_a_r10.json'}
d={k:json.loads(v.read_text()) for k,v in paths.items()}
ids={k:{r['id']:r for r in v['rows']} for k,v in d.items()};shared=set.intersection(*(set(v) for v in ids.values()));assert len(shared)==55
wall=(50,51,52,54);opening=(23,25,37,17)
def val(tag,id):
 r=ids[tag][id];q=r['sample']['plus_dx'];uv=q['mean_velocity_mps']
 return {'Sstar':q['exp_ratio'],'S':q['sim_ratio'],'k':q['tke_m2s2'],'ux':uv[0],'uy':uv[1],'direction_deg':math.degrees(math.atan2(uv[1],uv[0]))%360,'observed':r['after'],'fluid_corners':q['fluid_corners']}
def stats(tag,ls):
 v=[val(tag,i) for i in ls];return {'n':len(v),'MAE':statistics.mean(abs(q['Sstar']-q['observed']) for q in v),'mean_ratio':sum(q['Sstar'] for q in v)/sum(q['observed'] for q in v)}
def segments(tag):
 a=d[tag]['street50'];out=[];start=None
 for i,q in enumerate(a):
  neg=q['ux']<0 and q['fluid_corners']==8
  if neg and start is None:start=q['x']
  if start is not None and (not neg or i==len(a)-1):out.append([start,a[i-1]['x'] if not neg else q['x']]);start=None
 return out
summary={'tags':{},'wall':{},'paired':{},'profiles_present':{},'profile_comparison':[]}
for tag in d:
 summary['tags'][tag]={'wall':stats(tag,wall),'open':stats(tag,opening),'subset55':stats(tag,sorted(shared)),'street50':segments(tag),'upstream':d[tag]['upstream']}
for id in wall:
 summary['wall'][str(id)]={tag:val(tag,id) for tag in d}
 summary['paired'][str(id)]={
  'C05-C1_Sstar':val('C05',id)['Sstar']-val('C1',id)['Sstar'],
  'E05-E1_Sstar':val('E05',id)['Sstar']-val('E1',id)['Sstar'],
  'building_residual':(val('C05',id)['Sstar']-val('C1',id)['Sstar'])-(val('E05',id)['Sstar']-val('E1',id)['Sstar']),
  'C1G0-C1_Sstar':val('C1G0',id)['Sstar']-val('C1',id)['Sstar']}
rows=[]
for tag,v in d.items():
 pp={(q['x'],q['z_agl']):q for q in v['profiles']};summary['profiles_present'][tag]=len(pp)
 for x in (5.,15.,25.,35.,42.):
  for z in range(1,31):
   q=pp.get((x,z));rows.append({'tag':tag,'x_m':x,'z_m':z,'U_mps':q['U_mps'] if q else '', 'k_m2s2':q['k_m2s2'] if q else '', 'availability':'measured' if q else 'not saved in prior stage'})
for x in (5.,15.,25.,35.,42.):
 for z in range(1,31):
  item={'x':x,'z':z}
  for tag in d:
   p=next((q for q in d[tag]['profiles'] if q['x']==x and q['z_agl']==z),None)
   if p:item[tag+'_U']=p['U_mps'];item[tag+'_k']=p['k_m2s2']
  summary['profile_comparison'].append(item)
with (R/'profiles_five_stations.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['tag','x_m','z_m','U_mps','k_m2s2','availability']);w.writeheader();w.writerows(rows)
(R/'split_metrics.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print('WALL',json.dumps(summary['wall'],ensure_ascii=False))
print('PAIRED',json.dumps(summary['paired']))
print('STATS',json.dumps({t:{k:v for k,v in summary['tags'][t].items() if k!='upstream'} for t in d}))
print('PROFILES',summary['profiles_present'])

"""R5 descriptive within-area bins; spatial block bootstrap; never pool event gradients."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,collections,csv
from pathlib import Path
import numpy as np
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
rows=json.loads((P/'r5_buildings_modeled.json').read_text())
x={r['building_id']:r['label'] for r in json.loads((P/'r5_raw_20230831-Jena-SteinhatcheeRiverSouth.geo.tif_20230831a_RGB.geo.tif.json').read_text())}
y={r['building_id']:r['label'] for r in json.loads((P/'r5_raw_20230831-Jena-SteinhatcheeRiverSouth.geo.tif_20230902a_RGB.geo.tif.json').read_text())}
conflicts={i for i in x.keys()&y.keys() if x[i]!=y[i]}
assert len(conflicts)==10
valid={'no damage':0,'minor damage':1,'major damage':2,'destroyed':3}
for r in rows:
 r['view_conflict']=r['building_id'] in conflicts if r['event']=='IDALIA' else False
 r['eligible_label']=r['label'] in valid and not r['view_conflict']
 r['damage_ge_minor']=int(valid[r['label']]>=1) if r['eligible_label'] else None
 r['damage_ge_major']=int(valid[r['label']]>=2) if r['eligible_label'] else None
 t=Transformer.from_crs('EPSG:4326','EPSG:32617',always_xy=True);xx,yy=t.transform(r['lon'],r['lat'])
 r['block_500m']=f'{int(xx//500)}_{int(yy//500)}'
assert len(rows)==len({r['building_id'] for r in rows})
with (P/'r5_buildings_audit.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),extrasaction='ignore');w.writeheader();w.writerows(rows)
# Disjoint per-event/area fixed bins, deliberately no misleading across-event pooling.
BINS={'ian_harlem':[73.9,74,74.1,74.2,74.3],'idalia_jena':[55,56,57,58,59,60,61]}
summary={};rng=np.random.default_rng(20261014);fig,axes=plt.subplots(2,2,figsize=(12,8))
for j,area in enumerate(BINS):
 a=[r for r in rows if r['area']==area and r['eligible_label']];blocks=sorted({r['block_500m'] for r in a});bindex={b:[r for r in a if r['block_500m']==b] for b in blocks}
 stat={'raw_views':sum(r['area']==area for r in rows),'excluded_label_or_conflict':sum(r['area']==area and not r['eligible_label'] for r in rows),'usable':len(a),'blocks':len(blocks),'conflicts':sum(r['area']==area and r['view_conflict'] for r in rows),'water_screen_strict_n':sum(not r['water_risk_proxy'] for r in a),'water_screen_geo_only_n':sum(not r['water_risk_geo_only'] for r in a),'forecast_nonzero_n':sum(r['nhc_forecast_inundation_class']>0 for r in a),'bins':[]}
 edges=BINS[area]
 for lo,hi in zip(edges[:-1],edges[1:]):
  members=[r for r in a if lo<=r['model_gust_mps']<hi]
  out={'low_mps':lo,'high_mps':hi,'n':len(members),'blocks':len(set(r['block_500m'] for r in members))}
  for threshold,key in [('minor','damage_ge_minor'),('major','damage_ge_major')]:
   out[f'{threshold}_n']=sum(r[key] for r in members)
   out[f'{threshold}_rate']=sum(r[key] for r in members)/len(members) if members else None
   sims=[]
   # Resample entire area's spatial blocks; retain bins as defined in original coordinates.
   for iteration in range(600):
    sampled=[r for ix in rng.integers(0,len(blocks),len(blocks)) for r in bindex[blocks[ix]] if lo<=r['model_gust_mps']<hi]
    if sampled:sims.append(np.mean([r[key] for r in sampled]))
   out[f'{threshold}_ci_2p5']=float(np.quantile(sims,.025)) if sims else None
   out[f'{threshold}_ci_97p5']=float(np.quantile(sims,.975)) if sims else None
  stat['bins'].append(out)
  print(area,lo,hi,'n',len(members),'rates',out['minor_rate'],out['major_rate'],'blocks',out['blocks'],flush=True)
 for col,threshold in enumerate(['minor','major']):
  ax=axes[j,col];bb=[q for q in stat['bins'] if q['n']]
  mid=np.array([(q['low_mps']+q['high_mps'])/2 for q in bb]);vals=[q[f'{threshold}_rate'] for q in bb]
  lows=[q[f'{threshold}_ci_2p5'] if q[f'{threshold}_ci_2p5'] is not None else q[f'{threshold}_rate'] for q in bb]
  highs=[q[f'{threshold}_ci_97p5'] if q[f'{threshold}_ci_97p5'] is not None else q[f'{threshold}_rate'] for q in bb]
  ax.errorbar(mid,vals,yerr=[np.array(vals)-lows,np.array(highs)-vals],fmt='o-',capsize=3,color='#22577a')
  for xx,yy,q in zip(mid,vals,bb):ax.annotate(f"n={q['n']}; c={q['blocks']}",(xx,yy),xytext=(3,6),textcoords='offset points',fontsize=7)
  ax.set(xlabel='H2 reconstructed P2 peak gust (m/s; not measured)',ylabel=f'Visible damage >= {threshold} fraction',title=f'{area}: all surveyed, potential-water risk')
  ax.set_ylim(-.06,1.08);ax.grid(alpha=.2)
 summary[area]=stat
fig.text(.5,.01,'CRASAR-U-DROIDs labels CC BY 4.0; H2 Holland+residual / NHC track; USGS 3DEP and NHC potential surge screen.\nAll bins include suspected water exposure; reconstructed gust is not measured, and event/point peak may be biased.',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'r5_damage_probability_exploratory.png',dpi=160);plt.close(fig)
summary['water_risk_proxy']='STRICT: NHC potential surge class > 0 OR 3DEP bare-earth elevation <3 m OR approximate NE10m shore distance <5 km; not an observed inundation diagnosis.'
summary['geo_only_sensitivity']='3DEP elevation <2 m OR approximate shoreline <3 km, ignores NHC potential surge; not proven water-free.'
summary['bootstrap']='600 resamples of 500m UTM blocks within each survey area, seed 20261014; conditional label uncertainty only, not reconstruction/model or survey selection error.'
(P/'r5_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:{x:v for x,v in val.items() if x!='bins'} for k,val in summary.items() if isinstance(val,dict)},indent=2))

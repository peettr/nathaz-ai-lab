# 六审 f3df5c63 裁决时的只读敏感性（Lead，事后，不进主判）：按 WMO OSCAR 测风高度把 WN（及可选插值）做中性对数律换算，重算四项
import csv,math,collections,json,sys
from pathlib import Path
D=Path(sys.argv[1])
H={r['station']:float(r['wind_speed_sensor_height_m']) for r in csv.DictReader(open(D/'oscar_heights_f3df5c63.csv'))}
R=list(csv.DictReader(open(D/'paired_main_v3.csv')))
for r in R:
  for k in('obs_ms','p90','bilinear_ms','mos_ms','wn_ms'): r[k]=float(r[k])
def fit_mos(rows,col):
  g=collections.defaultdict(list)
  for r in rows:
    if r['period']=='train': g[(r['station'],r['wn_sector'])].append((r[col],r['obs_ms']))
  co={}
  for k,v in g.items():
    if len(v)<2: continue
    n=len(v);sx=sum(a for a,_ in v);sy=sum(b for _,b in v);sxx=sum(a*a for a,_ in v);sxy=sum(a*b for a,b in v)
    den=n*sxx-sx*sx; a=(n*sxy-sx*sy)/den if den else 0; co[k]=(a,(sy-a*sx)/n)
  return co
out={}
for z0 in (0.01,0.03,0.1):
  for both in (False,True):
    f={s:math.log(h/z0)/math.log(10/z0) for s,h in H.items()}
    rows=[dict(r) for r in R]
    for r in rows:
      r['wn']=r['wn_ms']*f[r['station']]; r['bil']=r['bilinear_ms']*(f[r['station']] if both else 1)
    co=fit_mos(rows,'wn')
    for r in rows:
      a,b=co.get((r['station'],r['wn_sector']),(None,None)); r['wnmos']=max(0,a*r['wn']+b) if a is not None else None
    t=[r for r in rows if r['period']=='test']; s=[r for r in t if r['obs_ms']>=r['p90']]
    mae=lambda rs,c:sum(abs(r[c]-r['obs_ms']) for r in rs if r[c] is not None)/len([r for r in rs if r[c] is not None])
    g=collections.defaultdict(list)
    for r in s: g[r['station']].append(r)
    # MOS on bilinear: if 'both', re-fit bilinear MOS too (invariant), else original
    R1=1-mae(s,'wn')/mae(s,'bil'); wins=sum(mae(v,'wn')<mae(v,'bil') for v in g.values())
    G3=(mae(s,'wnmos'),mae(s,'mos_ms')); G4=(mae(t,'wn'),mae(t,'bil'))
    out[f'z0={z0},scale_bilinear={both}']={'R1':R1,'wins':wins,'G3_wnmos_vs_mos':G3,'G4_wn_vs_bil':G4,
      'gates':[R1>=.15,wins>=8,G3[0]<G3[1],G4[0]<=G4[1]]}
Path(D/'sens_height_f3df5c63.json').write_text(json.dumps(out,indent=1,ensure_ascii=False)); print(json.dumps(out,indent=1))

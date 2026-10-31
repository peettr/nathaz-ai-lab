import csv,math,json
from pathlib import Path
root=Path(__file__).resolve().parent/'gate0_v4_results'
data={}
for nz in (10,20):
 for q in (.25,.75):
  name=f'z{nz}_q{str(q).replace(".","p")}'
  rows=list(csv.reader((root/(name+'.csv')).open()))
  profile=[(int(r[1]),float(r[2])) for r in rows if r[0]=='PROFILE' and r[1].isdigit()]
  zlo=1-q;zhi=nz-1.5;force=2e-6;nu=.1
  err=[v-force/(2*nu)*(z-zlo)*(zhi-z) for z,v in profile]
  ana=[force/(2*nu)*(z-zlo)*(zhi-z) for z,v in profile]
  l2=math.sqrt(sum(e*e for e in err)/len(err)); rel=l2/math.sqrt(sum(a*a for a in ana)/len(ana))
  data[name]={'L2_abs':l2,'L2_relative':rel,'first':profile[0],'fallback':[r for r in rows if r[0]=='FALLBACK'][0][1:]}
for q in (.25,.75):
 n0=f'z10_q{str(q).replace(".","p")}'; n1=f'z20_q{str(q).replace(".","p")}'
 data[f'order_q{q}']=math.log(data[n0]['L2_relative']/data[n1]['L2_relative'],2)
r=list(csv.reader((root/'closed_z20.csv').open()));s=[(int(v[0]),float(v[4])) for v in r if v[0].isdigit()]
data['closed']={'mass_initial':s[0],'mass_final':s[-1],'max_abs_delta':max(abs(x[1]-s[0][1]) for x in s),'fallback':[v for v in r if v[0]=='FALLBACK'][0][1:]}
(root/'metrics.json').write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2))

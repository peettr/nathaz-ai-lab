import csv,math,json
from pathlib import Path
p=Path(__file__).resolve().parent/'gate0_scaled_results';data={}
for q in (.25,.75):
 for nz in (10,18):
  tag=f'z{nz}_q{str(q).replace(".","p")}'
  rows=list(csv.reader((p/(tag+'.csv')).open()));points=[(int(r[1]),float(r[2])) for r in rows if r[0]=='PROFILE' and r[1].isdigit()]
  h0=7.5+q;h=nz-2.5+q;ratio=h/h0;nu=.1*ratio;f=2e-6/ratio
  ana=[f/(2*nu)*(z-(1-q))*(nz-1.5-z) for z,v in points];obs=[v for z,v in points]
  l2=math.sqrt(sum((v-u)**2 for u,v in zip(ana,obs))/len(obs));rel=math.sqrt(sum((v-u)**2 for u,v in zip(ana,obs))/sum(u*u for u in ana))
  data[tag]={'nu':nu,'force':f,'relative_L2':rel,'absolute_L2':l2,'fallback':[r for r in rows if r[0]=='FALLBACK'][0][1:]}
 a=data[f'z10_q{str(q).replace(".","p")}']['relative_L2'];b=data[f'z18_q{str(q).replace(".","p")}']['relative_L2']
 data[f'order_q{q}']=math.log(a/b)/math.log((15.5+q)/(7.5+q))
(p/'metrics.json').write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2))

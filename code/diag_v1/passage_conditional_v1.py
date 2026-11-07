"""Aggregate conditional native-node intensity at passage, preserving site multiplicity."""
import csv,collections,numpy as np,pathlib
P=pathlib.Path(__file__).resolve().parent
rows=list(csv.DictReader(open(P/'passage_events_v1.csv')));out=[]
segs=('TX','LA_to_Panhandle','FL_peninsula','Carolinas')
for seg in segs:
 for zone in ('RMW_le1','RMW_1to3','km_le50','km_le100'):
  for source,period in [('RAFT','all'),('STORM','all'),('HURDAT2','1979-2018'),('HURDAT2','1988-2018')]:
   for cut,label in [(35,'TS'),(64,'Cat1+'),(96,'Cat3+'),(114,'Cat4-5')]:
    selected=[r for r in rows if r['segment']==seg and r['zone']==zone and r['source']==source and float(r['vmax_kt'])>=cut and (source!='HURDAT2' or period=='1979-2018' or int(r['year'])>=1988)]
    v=np.array([float(r['vmax_kt']) for r in selected]);dp=np.array([float(r['dp1010_hpa']) for r in selected if r['dp1010_hpa']]);q=lambda x,p:float(np.quantile(x,p)) if len(x) else ''
    out.append(dict(source=source,period=period,segment=seg,zone=zone,threshold=label,site_event_n=len(v),dp_valid_n=len(dp),v_p50=q(v,.5),v_p90=q(v,.9),v_p99=q(v,.99),dp_p50=q(dp,.5),dp_p90=q(dp,.9),dp_p99=q(dp,.99)))
with open(P/'passage_conditional_v1.csv','x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
for zone in ['km_le100','RMW_1to3']:
 print('\n',zone)
 for seg in segs:
  for source,period in [('RAFT','all'),('STORM','all'),('HURDAT2','1988-2018')]:
   r=next(x for x in out if (x['segment'],x['zone'],x['source'],x['period'],x['threshold'])==(seg,zone,source,period,'TS'))
   print(seg,source,'N',r['site_event_n'],'v',round(r['v_p50'],1),round(r['v_p90'],1),round(r['v_p99'],1),'dp',round(r['dp_p50'],1) if r['dp_p50']!='' else None,round(r['dp_p90'],1) if r['dp_p90']!='' else None,round(r['dp_p99'],1) if r['dp_p99']!='' else None)

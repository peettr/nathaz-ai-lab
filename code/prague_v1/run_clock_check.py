"""Compare QC hourly PVK winds to LKPR UTC METAR under clock shifts."""
import json,csv,math,statistics,datetime as dt
from pathlib import Path
R=Path('/content/prague_qc')
obs={}
for m in ('04','05','06','07','08','09'):
 p=R/f'qc_2022{m}.json'
 if not p.exists():raise RuntimeError(f'QC not finished: {p}')
 data=json.loads(p.read_text());obs.update({dt.datetime.fromisoformat(k):v for k,v in data['hours'].items()})
air={}
with open('/content/lkpr.csv') as f:
 for row in csv.DictReader(f):
  try: t=dt.datetime.strptime(row['valid'],'%Y-%m-%d %H:%M');v=float(row['sknt'])*0.514444
  except (ValueError,KeyError):continue
  key=t.replace(minute=0)
  air.setdefault(key,[]).append(v)
air={k:sum(v)/len(v) for k,v in air.items()}
def corr(x,y):
 ax=sum(x)/len(x);ay=sum(y)/len(y)
 return sum((a-ax)*(b-ay) for a,b in zip(x,y))/math.sqrt(sum((a-ax)**2 for a in x)*sum((b-ay)**2 for b in y))
result={}
for shift in (-2,0,2):
 pairs=[(v,air[t+dt.timedelta(hours=shift)]) for t,v in obs.items() if t+dt.timedelta(hours=shift) in air]
 result[str(shift)]={'n':len(pairs),'r_hourly':corr(*zip(*pairs)),'mean_lidar':statistics.mean(a for a,b in pairs),'mean_airport':statistics.mean(b for a,b in pairs)}
# Diurnal mean separately: clock evidence is weak because geography and land surface differ.
for shift in (-2,0,2):
 xx=[];yy=[]
 for h in range(24):
  a=[v for t,v in obs.items() if t.hour==h]
  b=[v for t,v in air.items() if t.hour==(h+shift)%24]
  xx.append(statistics.mean(a));yy.append(statistics.mean(b))
 result[str(shift)]['r_diurnal']=corr(xx,yy)
result['lidar_diurnal_utc_like']={str(h):statistics.mean(v for t,v in obs.items() if t.hour==h) for h in range(24)}
result['airport_diurnal_utc']={str(h):statistics.mean(v for t,v in air.items() if t.hour==h) for h in range(24)}
(R/'clock_check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

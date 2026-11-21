"""Audit denominator of native-node <=500 km cohort for passage conditioning."""
import csv,pathlib,collections,datetime,numpy as np
P=pathlib.Path(__file__).resolve().parent;B=P.parent;s=list(csv.DictReader(open(P/'sites_min.csv')));la=np.array([float(x['lat']) for x in s]);lo=np.array([float(x['lon']) for x in s]);eligible=set()
def near(lat,lon):
 a=np.radians(np.array(lat)[:,None]-la);b=np.radians(np.array(lon)[:,None]-lo);q=np.sin(a/2)**2+np.cos(np.radians(lat)[:,None])*np.cos(np.radians(la))*np.sin(b/2)**2
 return bool(np.any(12742*np.arcsin(np.sqrt(np.clip(q,0,1)))<=500))
lines=open(B/'hurdat2-1851-2025-092326.txt').readlines();i=0;counts=collections.Counter()
while i<len(lines):
 h=[x.strip() for x in lines[i].split(',') if x.strip()];ident=h[0];n=int(h[2]);i+=1;rec=[]
 for line in lines[i:i+n]:
  t=[x.strip() for x in line.split(',')]
  try:
   dt=datetime.datetime.strptime(t[0]+t[1],'%Y%m%d%H%M');lat=float(t[4][:-1])*(1 if t[4][-1]=='N' else -1);lon=float(t[5][:-1])*(-1 if t[5][-1]=='W' else 1)
   rec.append((dt,t[3],lat,lon,int(t[6])))
  except(ValueError,IndexError):pass
 i+=n;year=int(ident[4:]);
 if year<1979 or year>2018:continue
 tropical=[r for r in rec if r[1] in ('TD','TS','HU')];ts=[r for r in rec if r[1] in ('TS','HU') and r[4]>=35]
 if not tropical or not ts or (tropical[-1][0]-tropical[0][0]).total_seconds()<86400:continue
 if near([r[2] for r in ts],[r[3] for r in ts]):
  counts['obs40']+=1
  if year>=1988:counts['obs31']+=1
print('obs 500km cohort',counts)
# RAFT/STORM native <=500 km counts audited in DIAG_inputs_v1.md and prior code.
base={'RAFT':15063,'STORM':32016,'HURDAT2_1979-2018':counts['obs40'],'HURDAT2_1988-2018':counts['obs31']}
rows=list(csv.DictReader(open(P/'passage_station_categories_v2.csv')))
for r in rows:
 key=r['source'] if r['source']!='HURDAT2' else 'HURDAT2_'+r['period']
 r['near500_denominator']=base[key];r['per_1000_near500']=float(r['n'])/base[key]*1000
with open(P/'passage_station_near500_v2.csv','x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with open(P/'passage_near500_denominators_v2.csv','x',newline='') as f:
 w=csv.writer(f);w.writerow(['source','native_500km_event_count']);w.writerows(base.items())

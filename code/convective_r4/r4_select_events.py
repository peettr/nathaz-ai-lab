"""R4 事件抽样（确定性，工作站 运行，只读第三轮清点结果）。"""
import csv,json,math,random,datetime as dt,pathlib,hashlib
R3=pathlib.Path(__file__).resolve().parent.parent/'convective_r3'; R4=pathlib.Path(__file__).resolve().parent
eli=[x for x in json.load(open(R3/'s0_eligible_1016.json')) if x['group']=='v1']
s2=[r for r in csv.DictReader(open(R3/'events_r3.csv')) if r['group']=='v1']
assert len(eli)==301 and len(s2)==120
s2ids={r['id'] for r in s2}; s2days={r['utc'][:10] for r in s2}
def init(u):
    t=dt.datetime.fromisoformat(u); c=(t+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0); return c-dt.timedelta(hours=2)
def km(a,b,c,d):
    a,b,c,d=map(math.radians,(a,b,c,d)); return 6371*2*math.asin(math.sqrt(math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2))
rem=[x for x in eli if str(x['id']) not in s2ids]; assert len(rem)==181
pool=[x for x in rem if x['hit']['utc'][:10] not in s2days]
# 再剔除与任一 S2 事件起报时刻相同（S2 已积分过该全场），或起报差 ≤2 h 且距离 ≤50 km 的
def clash(x):
    ix=init(x['hit']['utc'])
    return any(ix==init(r['utc']) or abs((ix-init(r['utc'])).total_seconds())<=7200 and km(float(x['lat']),float(x['lon']),float(r['lat']),float(r['lon']))<=50 for r in s2)
pool=[x for x in pool if not clash(x)]
same_init=[x for x in pool if any(init(x['hit']['utc'])==init(r['utc']) for r in s2)]
print('remaining',len(rem),'diff-day pool',len(pool),'same-init left',len(same_init),'days',len({x['hit']['utc'][:10] for x in pool}))
N=100; strata={}
for x in pool: strata.setdefault(x['hit']['utc'][:4],[]).append(x)
if len(pool)<=N: sel=sorted(pool,key=lambda x:str(x['id']))
else:
    alloc={y:int(N*len(v)/len(pool)) for y,v in strata.items()}; r=N-sum(alloc.values())
    for y in sorted(strata,key=lambda y:(-(N*len(strata[y])/len(pool)-alloc[y]),y))[:r]: alloc[y]+=1
    rng=random.Random(20261107); sel=[]
    for y in sorted(strata): sel+=rng.sample(sorted(strata[y],key=lambda x:str(x['id'])),alloc[y])
random.Random(20261107).shuffle(sel)   # 打乱单元顺序，避免按年排序
print('alloc',{y:sum(x['hit']['utc'][:4]==y for x in sel) for y in sorted(strata)},'pool by year',{y:len(v) for y,v in sorted(strata.items())})
f=['order','id','station','utc','obs_kt','lat','lon','state','year','ncei_url','iem_url','radar_url','grid_edge_km','metar']
with open(R4/'events_r4.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=f); w.writeheader()
    for i,x in enumerate(sel): w.writerow(dict(order=i,id=x['id'],station=x['station'],utc=x['hit']['utc'],obs_kt=x['hit']['kt'],lat=x['lat'],lon=x['lon'],state=x['state'],year=x['hit']['utc'][:4],ncei_url=x['ncei_url'],iem_url=x['iem_url'],radar_url=x['radar_evidence_url'],grid_edge_km=x['grid_edge_km'],metar=x['hit']['metar']))
json.dump([str(x['id']) for x in pool if x not in sel],open(R4/'events_r4_reserve_ids.json','w'))
print('sha events_r4.csv',hashlib.sha256(open(R4/'events_r4.csv','rb').read()).hexdigest())

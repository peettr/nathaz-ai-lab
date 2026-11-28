"""S3a 第三批（方案增补_S3a第三批事件_20261127.md）：自建 Storm Events 清单并下载 IEM 1 min。
用法: python3 -I s3a_r5_build_fetch.py <r3.csv> <r4.csv> <out_events.csv> <out_1min_dir> <tmpdir>"""
import sys,os,re,csv,gzip,json,math,time,random,urllib.request,datetime as dt,collections,shutil
r3,r4,OUTE,OUTD,TMP=sys.argv[1:6];os.makedirs(TMP,exist_ok=True);os.makedirs(OUTD,exist_ok=True);UA={'User-Agent':'research-client'}
def get(u,tries=3,binary=False):
    err=None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=120) as r:b=r.read();return b if binary else b.decode()
        except Exception as e:err=e;time.sleep(5*(i+1))
    raise err
BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
lst=get(BASE);YEARS=[2015,2016,2017,2018,2019,2020,2021,2023];ev=[];log=open(os.path.join(OUTD,'build_log.txt'),'w')
for y in YEARS:
    fs=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d%d_c\d+\.csv\.gz'%y,lst)));fn=fs[-1];p=os.path.join(TMP,fn)
    open(p,'wb').write(get(BASE+fn,binary=True));n=0
    with gzip.open(p,'rt',encoding='latin-1') as f:
        for r in csv.DictReader(f):
            if r['EVENT_TYPE']!='Thunderstorm Wind' or r['MAGNITUDE_TYPE']!='MG':continue
            try:mag=float(r['MAGNITUDE']);lat=float(r['BEGIN_LAT']);lon=float(r['BEGIN_LON'])
            except:continue
            if mag<50:continue
            m=re.search(r'(-?\d+)$',r['CZ_TIMEZONE'] or '')
            if not m:continue
            ym=r['BEGIN_YEARMONTH'];bt=int(r['BEGIN_TIME']);loc=dt.datetime(int(ym[:4]),int(ym[4:]),int(r['BEGIN_DAY']),bt//100,bt%100)
            ev.append(dict(id=r['EVENT_ID'],year=y,utc=loc-dt.timedelta(hours=int(m.group(1))),mag=mag,lat=lat,lon=lon));n+=1
    log.write(f'{fn} MG>=50 TSW events {n}\n');os.remove(p)
STATES='AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY'.split()
st=[]
for s in STATES:
    try:g=json.loads(get(f'https://mesonet.agron.iastate.edu/geojson/network/{s}_ASOS.geojson'))
    except Exception as e:log.write(f'station {s} fail {e}\n');continue
    for ft in g['features']:
        lon,lat=ft['geometry']['coordinates'][:2];st.append((ft['id'],lat,lon))
    time.sleep(.5)
log.write(f'stations {len(st)}\n')
def hav(a,b,c,d):
    R=6371.;p=math.radians;x=math.sin(p(c-a)/2)**2+math.cos(p(a))*math.cos(p(c))*math.sin(p(d-b)/2)**2;return 2*R*math.asin(math.sqrt(x))
used={(r['station'],r['utc'][:10]) for f in (r3,r4) for r in csv.DictReader(open(f))}
best={}
for e in ev:
    cand=[(hav(e['lat'],e['lon'],la,lo),sid) for sid,la,lo in st if abs(la-e['lat'])<0.2 and abs(lo-e['lon'])<0.3]
    if not cand:continue
    dkm,sid=min(cand)
    if dkm>10:continue
    k=(sid,e['utc'].strftime('%Y-%m-%d'))
    if k in used:continue
    if k not in best or e['mag']>best[k]['mag']:best[k]=dict(e,station=sid,dist_km=dkm)
sel=list(best.values());log.write(f'matched station-days {len(sel)}\n')
if len(sel)>800:
    rng=random.Random(0);by=collections.defaultdict(list)
    for e in sel:by[e['year']].append(e)
    out=[]
    for y,L in sorted(by.items()):k=round(800*len(L)/len(sel));rng.shuffle(L);out+=L[:k]
    sel=out
log.write(f'selected {len(sel)}\n');log.flush()
with open(OUTE,'w',newline='') as f:
    w=csv.writer(f);w.writerow(['id','station','utc','mag_kt','dist_km','year'])
    for e in sorted(sel,key=lambda e:e['utc']):w.writerow([e['id'],e['station'],e['utc'].isoformat(),e['mag'],round(e['dist_km'],2),e['year']])
shutil.rmtree(TMP,ignore_errors=True)
fl=open(os.path.join(OUTD,'fetch_log.csv'),'a');f2=lambda t:t.strftime('%Y-%m-%dT%H:%MZ')
for e in sel:
    p=os.path.join(OUTD,f"TS_{e['id']}_{e['station']}.csv")
    if os.path.exists(p):continue
    c=e['utc'];u=('https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?station=%s&vars=sknt&vars=gust_sknt&sts=%s&ets=%s&sample=1min&what=download&delim=comma&tz=UTC')%(e['station'],f2(c-dt.timedelta(hours=3)),f2(c+dt.timedelta(hours=3)))
    try:open(p,'w').write(get(u));fl.write(f"{e['id']},{e['station']},ok\n")
    except Exception as x:fl.write(f"{e['id']},{e['station']},fail,{x}\n")
    fl.flush();time.sleep(1)
print('done',len(sel))

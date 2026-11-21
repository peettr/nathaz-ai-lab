"""S3a-2 下载：雷暴组与良态大风组的 IEM ASOS 1 min 窗。用法: python3 -I s3a_asos_fetch.py <events_r3.csv> <outdir>"""
import sys,csv,os,time,urllib.request,datetime as dt,re
ev=list(csv.DictReader(open(sys.argv[1])));out=sys.argv[2];os.makedirs(out,exist_ok=True)
UA={'User-Agent':'research-client'}
def get(url,tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=60) as r:return r.read().decode()
        except Exception as e:time.sleep(5*(i+1));err=e
    raise err
def f(t):return t.strftime('%Y-%m-%dT%H:%MZ')
def one_min(st,c,path):
    if os.path.exists(path):return
    u=('https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?station=%s&vars=sknt&vars=gust_sknt&sts=%s&ets=%s'
       '&sample=1min&what=download&delim=comma&tz=UTC')%(st,f(c-dt.timedelta(hours=3)),f(c+dt.timedelta(hours=3)))
    open(path,'w').write(get(u));time.sleep(1)
BAD=re.compile(r'\b(\+|-|VC)?TS|\bCB\b|\bTCU\b|\bSQ\b')
log=open(os.path.join(out,'fetch_log.csv'),'a')
for e in ev:
    st=e['station'];c=dt.datetime.fromisoformat(e['utc']);eid=e['id']
    try:one_min(st,c,os.path.join(out,f'TS_{eid}_{st}.csv'))
    except Exception as x:log.write(f'TS,{eid},{st},fail,{x}\n');continue
    p=os.path.join(out,f'SYN_{eid}_{st}.csv')
    if os.path.exists(p):continue
    m0=c.replace(day=1,hour=0,minute=0,second=0);m1=(m0+dt.timedelta(days=32)).replace(day=1)
    try:
        txt=get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=sknt&data=metar&tz=Etc/UTC&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&sts=%s&ets=%s'%(st,f(m0),f(m1)))
        rows=[r for r in csv.DictReader(txt.splitlines()) if r.get('sknt','M') not in ('M','')];time.sleep(1)
        for r in rows:r['t']=dt.datetime.strptime(r['valid'],'%Y-%m-%d %H:%M');r['k']=float(r['sknt'])
        bad=[r['t'] for r in rows if BAD.search(r.get('metar',''))]
        cand=sorted([r for r in rows if r['k']>=15 and abs((r['t']-c).total_seconds())>6*3600
                     and not any(abs((r['t']-b).total_seconds())<=3*3600 for b in bad)
                     and r['t']-dt.timedelta(hours=3)>=m0 and r['t']+dt.timedelta(hours=3)<m1],key=lambda r:-r['k'])
        if not cand:log.write(f'SYN,{eid},{st},none,\n');continue
        one_min(st,cand[0]['t'],p);log.write(f'SYN,{eid},{st},ok,{cand[0]["t"].isoformat()} {cand[0]["k"]}\n')
    except Exception as x:log.write(f'SYN,{eid},{st},fail,{x}\n')
    log.flush()
print('done')

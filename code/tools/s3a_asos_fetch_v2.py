"""S3a-2 v2：只重选并下载良态大风组（修 CB/TCU 正则、先查天气、含 SPECI、按站+时刻去重、排除该站清单内任一雷暴 ±6 h）。
用法: python3 -I s3a_asos_fetch_v2.py <events_r3.csv> <outdir>"""
import sys,csv,os,time,urllib.request,datetime as dt,re,collections
ev=list(csv.DictReader(open(sys.argv[1])));out=sys.argv[2];os.makedirs(out,exist_ok=True)
UA={'User-Agent':'research-client'}
def get(url,tries=3):
    err=None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=60) as r:return r.read().decode()
        except Exception as e:time.sleep(5*(i+1));err=e
    raise err
f=lambda t:t.strftime('%Y-%m-%dT%H:%MZ')
BAD=re.compile(r'(\b(\+|-|VC)?TS)|CB\b|TCU\b|\bSQ\b')
ts_by_st=collections.defaultdict(list)
for e in ev:ts_by_st[e['station']].append(dt.datetime.fromisoformat(e['utc']))
used=set();log=open(os.path.join(out,'fetch_log_v2.csv'),'a')
for e in ev:
    st=e['station'];c=dt.datetime.fromisoformat(e['utc']);eid=e['id']
    m0=c.replace(day=1,hour=0,minute=0,second=0);m1=(m0+dt.timedelta(days=32)).replace(day=1)
    try:
        txt=get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=sknt&data=metar&tz=Etc/UTC&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&report_type=4&sts=%s&ets=%s'%(st,f(m0),f(m1)));time.sleep(1)
        allr=list(csv.DictReader(txt.splitlines()))
        for r in allr:r['t']=dt.datetime.strptime(r['valid'],'%Y-%m-%d %H:%M')
        bad=[r['t'] for r in allr if BAD.search(r.get('metar',''))]
        rows=[r for r in allr if r.get('sknt','M') not in ('M','')]
        for r in rows:r['k']=float(r['sknt'])
        cand=sorted([r for r in rows if r['k']>=15
            and all(abs((r['t']-x).total_seconds())>6*3600 for x in ts_by_st[st])
            and not any(abs((r['t']-b).total_seconds())<=3*3600 for b in bad)
            and r['t']-dt.timedelta(hours=3)>=m0 and r['t']+dt.timedelta(hours=3)<m1
            and (st,r['t'].strftime('%Y%m%d%H')) not in used],key=lambda r:-r['k'])
        if not cand:log.write(f'SYN,{eid},{st},none,\n');log.flush();continue
        t=cand[0]['t'];used.add((st,t.strftime('%Y%m%d%H')))
        p=os.path.join(out,f'SYN_{eid}_{st}.csv')
        if not os.path.exists(p):
            open(p,'w').write(get(('https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?station=%s&vars=sknt&vars=gust_sknt&sts=%s&ets=%s'
              '&sample=1min&what=download&delim=comma&tz=UTC')%(st,f(t-dt.timedelta(hours=3)),f(t+dt.timedelta(hours=3)))));time.sleep(1)
        log.write(f'SYN,{eid},{st},ok,{t.isoformat()} {cand[0]["k"]}\n')
    except Exception as x:log.write(f'SYN,{eid},{st},fail,{x}\n')
    log.flush()
print('done')

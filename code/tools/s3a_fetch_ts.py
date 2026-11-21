"""只下载雷暴组 ±3 h 的 IEM 1 min（sknt, gust_sknt）。用法: python3 -I s3a_fetch_ts.py <events.csv> <outdir>"""
import sys,csv,os,time,urllib.request,datetime as dt
ev=list(csv.DictReader(open(sys.argv[1])));out=sys.argv[2];os.makedirs(out,exist_ok=True);UA={'User-Agent':'research-client'}
f=lambda t:t.strftime('%Y-%m-%dT%H:%MZ');log=open(os.path.join(out,'fetch_log.csv'),'a')
for e in ev:
    st=e['station'];c=dt.datetime.fromisoformat(e['utc']);p=os.path.join(out,f"TS_{e['id']}_{st}.csv")
    if os.path.exists(p):continue
    u=('https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?station=%s&vars=sknt&vars=gust_sknt&sts=%s&ets=%s&sample=1min&what=download&delim=comma&tz=UTC')%(st,f(c-dt.timedelta(hours=3)),f(c+dt.timedelta(hours=3)))
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60) as r:open(p,'w').write(r.read().decode());log.write(f"{e['id']},{st},ok\n");break
        except Exception as x:time.sleep(5*(i+1));err=x
    else:log.write(f"{e['id']},{st},fail,{err}\n")
    log.flush();time.sleep(1)
print('done')

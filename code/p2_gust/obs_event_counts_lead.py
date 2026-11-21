import gzip,csv,collections,json,sys
P=sys.argv[1]
obs={}
with gzip.open(P,'rt') as f:
    for r in csv.DictReader(f):
        if r['source']!='GFS' or r['obs_6x10min_complete'] not in ('True','1','true'): continue
        k=(r['station'],r['valid_end_utc'])
        if k in obs: continue
        obs[k]=(r['season'],r['terrain'],float(r['obs_mean_ms']),float(r['obs_gust_1s_ms']))
seasons=sorted({v[0] for v in obs.values()}); print(seasons)
tr,te=seasons[:2],seasons[2]
by=collections.defaultdict(lambda:{'tr':[],'te':[],'te_mean':[]})
terr={}
for (s,t),(se,ter,m,g) in obs.items():
    terr[s]=ter
    if se in tr: by[s]['tr'].append(g)
    elif se==te: by[s]['te'].append(g); by[s]['te_mean'].append(m)
def q(v,p):
    v=sorted(v); i=p*(len(v)-1); lo=int(i); return v[lo]+(v[min(lo+1,len(v)-1)]-v[lo])*(i-lo)
out={}; tot=collections.Counter()
for s,d in sorted(by.items()):
    p95,p99=q(d['tr'],.95),q(d['tr'],.99)
    c={'n_te':len(d['te']),'P95':sum(g>=p95 for g in d['te']),'P99':sum(g>=p99 for g in d['te']),
       'S1_20.1':sum(g>=20.1 for g in d['te']),'S2_26.8':sum(g>=26.8 for g in d['te']),'S3_31.3':sum(g>=31.3 for g in d['te']),
       'S5_12.5':sum(g>=12.5 for g in d['te']),'S4_mean11.1':sum(m>=11.1 for m in d['te_mean']),'p95':round(p95,1),'p99':round(p99,1)}
    out[s]={'terrain':terr[s],**c}
    for k,v in c.items():
        if k not in('p95','p99'): tot[k]+=v
print(json.dumps(tot))
for k in ['P95','P99','S1_20.1','S2_26.8','S3_31.3','S5_12.5','S4_mean11.1']:
    print(k,'stations>=10 events:',sum(o[k]>=10 for o in out.values()))
json.dump(out,open('/tmp/p2scr/events.json','w'),indent=1)

import csv,json,urllib.request,sys,time
src=sys.argv[1]; out=sys.argv[2]
rows=list(csv.DictReader(open(src)))
cand=[r for r in rows if r['primary_eligible']=='no' and r['inventory_height_ft'] and r['inventory_commission'] and r['inventory_commission']<=r['landfall_utc'][:10]]
res=[]
cache={}
for r in cand:
    ic=r['icao']
    if ic not in cache:
        u=r['homr_url']; d=json.load(urllib.request.urlopen(u,timeout=60)); cache[ic]=d; time.sleep(0.5)
    d=cache[ic]; ev=r['landfall_utc'][:10]
    for s in d.get('stationCollection',{}).get('stations',[]):
        asos=[p['date'] for p in s.get('platforms',[]) if p.get('platform')=='ASOS']
        closing=[m['date']['beginDate'][:10] for m in s.get('remarks',[]) if 'CLOSING' in m.get('remark','').upper()]
        for a in asos:
            res.append(dict(event=r['event'],station=r['station'],ft=r['inventory_height_ft'],ncdc=s.get('ncdcStnId'),asos_begin=a.get('beginDate','')[:10],asos_end=a.get('endDate','')[:10],closing_remarks=';'.join(closing),event_date=ev,end_eq_coop_closing=str(a.get('endDate','')[:10] in closing)))
w=csv.DictWriter(open(out,'w'),fieldnames=list(res[0].keys()) if res else ['event']); w.writeheader(); [w.writerow(x) for x in res]
print(len(cand),'candidates'); [print(x) for x in res]

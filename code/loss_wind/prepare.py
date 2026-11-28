#!/usr/bin/env python3
"""Reproducible NCEI Storm Events sampling, 2018-2023."""
import csv, gzip, io, json, random, re, urllib.request, pathlib, hashlib, collections
HERE=pathlib.Path(__file__).parent
RAW=pathlib.Path('./.hermes/profiles/researchos-lab-ideas/cache/scratch/loss_wind_ncei')
RAW.mkdir(parents=True,exist_ok=True)
BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
s1='./16_PETW/02_Subprojects/SP1_Event_Classification_Reconstruction/07_Outputs/S1_Detectability_TX4_20261009/S1_ROWS_v1.2.csv'
ids={x['event_id'].split(':')[-1] for x in csv.DictReader(open(s1,encoding='utf-8-sig')) if x['event_id'].startswith('StormEvents:')}
listing=urllib.request.urlopen(BASE,timeout=45).read().decode()
rng=random.Random(20261014)
pools=collections.defaultdict(list); provenance=[]
for year in range(2018,2024):
    names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',listing)))
    assert names,year
    name=names[-1]; path=RAW/name
    if not path.exists():
        with urllib.request.urlopen(BASE+name,timeout=180) as response, open(path,'wb') as f:
            while True:
                block=response.read(1024*1024)
                if not block:break
                f.write(block)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    provenance.append(dict(year=year,url=BASE+name,sha256=digest,bytes=path.stat().st_size))
    with gzip.open(path,'rt',encoding='utf-8-sig',errors='replace',newline='') as stream:
        for row in csv.DictReader(stream):
            typ=row['EVENT_TYPE'].strip()
            if typ=='Thunderstorm Wind':haz='thunderstorm'
            elif typ in ('Hurricane (Typhoon)','Tropical Storm'):haz='tropical'
            elif typ=='High Wind' and int(row['BEGIN_YEARMONTH'][-2:]) in (10,11,12,1,2,3,4):haz='synoptic'
            else:continue
            text=(row.get('EVENT_NARRATIVE') or '').strip()
            if not text:continue
            damage=bool(re.search(r'\b(damag|destroy|fell|fallen|downed|uproot|snapp|broke|broken|topp|roof|power line|tree|barn|pole|structur|debris|shingle|fence|collapse|blown|blew|overturn|outage|lost power|windows?)',text,re.I))
            prop=(row.get('DAMAGE_PROPERTY') or '').strip()
            if not damage and not prop.strip('0. KMB$'):continue
            if haz=='synoptic' and re.search(r'\b(downslope|chinook|santa ana|sundowner|dust storm)\b',text,re.I):continue
            row['hazard']=haz;row['year']=year;row['s1_overlap']=str(row['EVENT_ID'] in ids)
            pools[haz].append(row)
(HERE/'source_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
selected=[]
for haz,n in (('thunderstorm',120),('tropical',90),('synoptic',90)):
    pool=pools[haz]
    if haz=='thunderstorm':
        overlap=[r for r in pool if r['s1_overlap']=='True'];other=[r for r in pool if r['s1_overlap']!='True']
        chosen=rng.sample(overlap,min(40,len(overlap)))
        other=[r for r in pool if r['EVENT_ID'] not in {a['EVENT_ID'] for a in chosen}]
        chosen+=rng.sample(other,n-len(chosen))
    else:chosen=rng.sample(pool,n)
    selected+=chosen
assert len(selected)==300 and len({r['EVENT_ID'] for r in selected})==300
cols=['EVENT_ID','hazard','year','s1_overlap','EVENT_TYPE','BEGIN_DATE_TIME','END_DATE_TIME','CZ_TIMEZONE','STATE','CZ_NAME','BEGIN_LOCATION','BEGIN_LAT','BEGIN_LON','END_LAT','END_LON','EVENT_NARRATIVE','MAGNITUDE','MAGNITUDE_TYPE','SOURCE','DAMAGE_PROPERTY']
for batch in range(3):
    subset=selected[batch*100:(batch+1)*100]
    with open(HERE/f'sample_{batch+1}.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r.get(k,'') for k in cols} for r in subset)
(HERE/'sampling_counts.json').write_text(json.dumps({'seed':20261014,'eligible':{h:len(pools[h]) for h in pools},'selected':dict(collections.Counter(r['hazard'] for r in selected)),'s1_eligible':len([r for r in pools['thunderstorm'] if r['s1_overlap']=='True']),'s1_selected':len([r for r in selected if r['s1_overlap']=='True'])},indent=2)+'\n')
print((HERE/'sampling_counts.json').read_text())

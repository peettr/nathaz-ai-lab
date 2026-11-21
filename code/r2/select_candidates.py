"""Candidate-only Storm Events inventory; no forecast scores or verified negatives."""
import csv, gzip, io, re, requests, datetime as dt, pathlib, collections
BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
ROOT=pathlib.Path(__file__).parent
index=requests.get(BASE, timeout=60).text
out=[]; counts=collections.Counter()
for year in range(2022,2027):
    names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',index)))
    if not names: print('MISSING_YEAR',year,flush=True); continue
    url=BASE+names[-1]
    payload=requests.get(url,timeout=180);payload.raise_for_status()
    rows=csv.DictReader(io.StringIO(gzip.decompress(payload.content).decode('utf-8-sig')))
    print('SOURCE',url,'compressed_bytes',len(payload.content),flush=True)
    for row in rows:
        if row['EVENT_TYPE']!='Thunderstorm Wind' or row['MAGNITUDE_TYPE']!='MG':continue
        if float(row.get('MAGNITUDE') or 0)<50:continue
        if not re.search(r'ASOS',row.get('SOURCE','')+' '+row.get('EVENT_NARRATIVE',''),re.I):continue
        station=re.match(r'^\(([A-Z0-9]{3})\)',row['BEGIN_LOCATION'])
        if not station:continue
        try:
            lat=float(row['BEGIN_LAT']);lon=float(row['BEGIN_LON'])
            if not (34<lat<44 and -102<lon<-91):continue # V1 published central-domain conservative envelope
            raw=dt.datetime.strptime(row['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S')
            offset=re.search(r'([+-]\d{1,2})$',row['CZ_TIMEZONE'])
            if not offset:continue
            utc=raw-dt.timedelta(hours=int(offset.group(1)))
        except (ValueError,KeyError):continue
        out.append({'id':row['EVENT_ID'],'station':station.group(1),'peak_candidate_utc':utc.isoformat()+'Z','gust_kt':row['MAGNITUDE'],'lat':lat,'lon':lon,'state':row['STATE'],'source':row['SOURCE'],'narrative':row['EVENT_NARRATIVE'],'url':url,'year':year,'qc':'UNVERIFIED_NOAA_TIME_AND_ASOS_1MIN'})
        counts[year]+=1
with (ROOT/'candidate_catalog.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=out[0].keys());w.writeheader();w.writerows(out)
print('COUNTS',dict(counts),'total',len(out),'unique_days',len({r['peak_candidate_utc'][:10] for r in out}),flush=True)

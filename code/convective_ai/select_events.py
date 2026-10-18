"""Select measured ASOS thunderstorm-wind reports from NOAA annual bulk CSV."""
import csv, gzip, io, re, urllib.request, json
BASE='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
INDEX=urllib.request.urlopen(BASE,timeout=60).read().decode()
for year in (2023,2024):
    name=re.search(r'StormEvents_details-ftp_v1\.0_d'+str(year)+r'_c\d+\.csv\.gz',INDEX).group()
    rows=csv.DictReader(io.StringIO(gzip.decompress(urllib.request.urlopen(BASE+name,timeout=120).read()).decode('utf-8-sig')))
    selected=[]
    for r in rows:
        if r['EVENT_TYPE']!='Thunderstorm Wind' or r['MAGNITUDE_TYPE']!='MG' or float(r.get('MAGNITUDE') or 0)<50:continue
        if not (34<float(r.get('BEGIN_LAT') or 0)<44 and -102<float(r.get('BEGIN_LON') or 0)<-91):continue
        if not re.search(r'ASOS|airport',r['EVENT_NARRATIVE']+' '+r['SOURCE']+' '+r['BEGIN_LOCATION'],re.I):continue
        selected.append({k:r[k] for k in ('EVENT_ID','BEGIN_DATE_TIME','CZ_TIMEZONE','STATE','BEGIN_LOCATION','BEGIN_LAT','BEGIN_LON','MAGNITUDE','MAGNITUDE_TYPE','SOURCE','EVENT_NARRATIVE')})
    print(year,name,'selected',len(selected))
    for r in selected[:90]:print(json.dumps(r,ensure_ascii=False))

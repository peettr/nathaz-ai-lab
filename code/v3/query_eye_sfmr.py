import csv,sys,datetime as dt,urllib.request,urllib.parse,concurrent.futures as cf
rows=[r for r in csv.DictReader(open(sys.argv[1])) if r['eye_in_acq']=='True' and r['acquisition_start_time']>='2018']
def one(r):
    t=dt.datetime.fromisoformat(r['acquisition_start_time'])
    a=(t-dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ');b=(t+dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
    q='flight_id,tropical_cyclone_name&time>=%s&time<=%s&distinct()'%(a,b)
    url='https://erddap.aoml.noaa.gov/hdb/erddap/tabledap/sfmr_2018_2022.csv?'+urllib.parse.quote(q,safe='=&(),')
    try:
        txt=urllib.request.urlopen(url,timeout=40).read().decode().splitlines()[2:]
        fl=[l.split(',')[0] for l in txt if r['cyclone_name'].lower() in l.lower()]
    except Exception as e: fl=['ERR']
    return [r['cyclone_name'],r['sid'],r['acquisition_start_time'],r['mission'],r['vmax (m/s)'],';'.join(fl)]
out=csv.writer(open('eye_sfmr.csv','w',newline=''));out.writerow(['name','sid','time','mission','vmax','flights'])
for x in cf.ThreadPoolExecutor(12).map(one,rows): out.writerow(x)

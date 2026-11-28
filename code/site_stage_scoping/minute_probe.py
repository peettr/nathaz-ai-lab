"""Small, read-only IEM NCEI 1-min probes; no raw rows written to disk."""
import csv, io, urllib.parse, urllib.request, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
SIDS='MSP DSM OMA DTW PIT ALB DFW AUS FSD FAR ICT STL IND CLE BDL'.split()
windows=[('2000-01-01','2000-01-02'),('2001-01-01','2001-01-02'),('2005-01-01','2005-01-02'),('2009-01-01','2009-01-02'),('2010-01-01','2010-01-08')]
rows=[]
for sid in SIDS:
 for a,b in windows:
  params={'station':sid,'vars':'sknt,gust_sknt','sts':a+'T00:00Z','ets':b+'T00:00Z','tz':'UTC','what':'download'}
  url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?'+urllib.parse.urlencode(params)
  out={'station':'K'+sid,'start_utc':a,'end_utc_exclusive':b,'url':url}
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AI-weather-research-readonly/1.0'}),timeout=60) as r:
    inp=io.TextIOWrapper(r,encoding='utf-8');reader=csv.DictReader(inp)
    if not reader.fieldnames or 'sknt' not in reader.fieldnames:raise ValueError(str(reader.fieldnames))
    n=wind=gust=0;first=last=None
    for x in reader:
     n+=1;first=first or x.get('valid(UTC)');last=x.get('valid(UTC)')
     wind+= x['sknt'] not in ('','M','NA','None');gust+=x['gust_sknt'] not in ('','M','NA','None')
    out.update(rows=n,nonmissing_sknt=wind,nonmissing_gust_sknt=gust,first_row=first,last_row=last)
  except Exception as e:out['error']=str(e)
  rows.append(out)
  print(sid,a,out.get('rows'),out.get('error'),flush=True)
  time.sleep(.15)
with (HERE/'minute_probe.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));w.writeheader();w.writerows(rows)

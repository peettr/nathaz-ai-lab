"""IEM cold-season streaming audit; raw rows never persisted. Run on Colab CPU.
One station-season at a time, append verified summary atomically; errors are explicit.
"""
import csv, io, json, os, time, urllib.parse, urllib.request, datetime as dt, traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
ROOT=Path('/content/site_stage_audit');ROOT.mkdir(exist_ok=True)
SIDS='MSP DSM OMA DTW PIT ALB DFW AUS FSD FAR ICT STL IND CLE BDL'.split()
MISSING={'','M','NA','None','null','nan','-9999'}
HEAD={'User-Agent':'PETW-AIWeather-site-stage-audit/1.0 (research, IEM)'}
def get(url):
 for trial in range(4):
  try:
   return urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=180)
  except Exception as e:
   if trial==3:raise
   time.sleep(4*(trial+1))
def fmt(t):return t.strftime('%Y-%m-%dT%H:%MZ')
def numeric(s):
 try:
  if s is None or s.strip() in MISSING:return None
  v=float(s)
  return v if 0<=v<300 else None
 except (ValueError,AttributeError):return None
def minute_time(s):
 if not s:return None
 try:return dt.datetime.strptime(s[:16],'%Y-%m-%d %H:%M')
 except ValueError:
  try:return dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=None)
  except ValueError:return None
def run(sid,year):
 start=dt.datetime(year,10,1);end=dt.datetime(year+1,4,1);expected=int((end-start).total_seconds()//60)
 params={'station':sid,'vars':'sknt,gust_sknt','sts':fmt(start),'ets':fmt(end),'tz':'UTC','what':'download'}
 minute_url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?'+urllib.parse.urlencode(params)
 seen=set(); wind=set(); gust=set(); peaks=[]; first=last=None; raw=0
 with get(minute_url) as resp:
  reader=csv.DictReader(io.TextIOWrapper(resp,encoding='utf-8',errors='replace'))
  assert reader.fieldnames and 'sknt' in reader.fieldnames and 'gust_sknt' in reader.fieldnames,reader.fieldnames
  for r in reader:
   t=minute_time(r.get('valid(UTC)') or r.get('valid'))
   if t is None or not start<=t<end:continue
   k=int((t-start).total_seconds()//60)
   raw+=1;seen.add(k);first=first or fmt(t);last=fmt(t)
   if numeric(r.get('sknt')) is not None:wind.add(k)
   v=numeric(r.get('gust_sknt'))
   if v is not None:gust.add(k);peaks.append((v,k))
 def gap(arr):
  prev=-1;best=0
  for x in sorted(arr):best=max(best,x-prev-1);prev=x
  return max(best,expected-prev-1)
 def near(k,arr):
  a=max(0,k-360);b=min(expected-1,k+360)
  return b-a+1-sum(a<=x<=b for x in arr)
 peak=max(peaks,key=lambda x:(x[0],-x[1])) if peaks else None
 data={'station':'K'+sid,'season':f'{year}/{str(year+1)[-2:]}','start_utc':fmt(start),'end_utc_exclusive':fmt(end),'expected_minutes':expected,'raw_rows':raw,'observed_unique_minutes':len(seen),'wind_valid_minutes':len(wind),'gust_nonempty_minutes':len(gust),'row_coverage':len(seen)/expected,'wind_coverage':len(wind)/expected,'gust_nonempty_fraction':len(gust)/expected,'max_gap_rows_min':gap(seen),'max_gap_wind_min':gap(wind),'minute_peak_knots':peak[0] if peak else None,'minute_peak_utc':fmt(start+dt.timedelta(minutes=peak[1])) if peak else None,'peak_plusminus6h_missing_rows':near(peak[1],seen) if peak else None,'peak_plusminus6h_missing_wind':near(peak[1],wind) if peak else None,'peak_plusminus6h_missing_gust':near(peak[1],gust) if peak else None,'first_row_utc':first,'last_row_utc':last,'minute_url':minute_url}
 # seasonal METAR: keep reports only near seasonal peaks (and strongest reports), never raw archive
 mparams={'station':sid,'data':'gust,peak_wind_gust,peak_wind_time,wxcodes,metar','sts':fmt(start),'ets':fmt(end),'tz':'UTC','report_type':'1,3,4','format':'onlycomma','missing':'M'}
 metar_url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(mparams)
 best={'gust':None,'peak_wind_gust':None};report_n=0;times=[];mrows=[]
 with get(metar_url) as resp:
  reader=csv.DictReader(io.TextIOWrapper(resp,encoding='utf-8',errors='replace'))
  assert reader.fieldnames and 'valid' in reader.fieldnames,reader.fieldnames
  for r in reader:
   t=minute_time(r.get('valid'))
   if t is None or not start<=t<end:continue
   report_n+=1;times.append(t)
   for col in best:
    v=numeric(r.get(col))
    if v is not None and (best[col] is None or v>best[col]['knots']):
     best[col]={'knots':v,'report_utc':fmt(t),'peak_wind_time_raw':r.get('peak_wind_time'),'metar':(r.get('metar') or '')[:600],'wxcodes':r.get('wxcodes')}
   if peak and abs((t-(start+dt.timedelta(minutes=peak[1]))).total_seconds())<=7200:
    mrows.append({'report_utc':fmt(t),'wxcodes':r.get('wxcodes'),'metar':(r.get('metar') or '')[:600]})
 data.update(metar_report_count=report_n,metar_max_gust=best['gust'],metar_max_pk=best['peak_wind_gust'],metar_url=metar_url,minute_peak_near_metars=mrows)
 return data

def main():
 output=ROOT/'season_audit.jsonl'; errs=ROOT/'errors.jsonl'
 done=set()
 if output.exists():
  for line in output.read_text().splitlines():
   try:
    r=json.loads(line);done.add((r['station'][1:],int(r['season'][:4])))
   except Exception:pass
 print('RESUME',len(done),flush=True)
 for y in range(2000,2024):
  for sid in SIDS:
   if (sid,y) in done:continue
   try:
    t=time.monotonic();d=run(sid,y)
    with output.open('a') as f:f.write(json.dumps(d,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    done.add((sid,y));print('OK',sid,y,d['raw_rows'],d['row_coverage'],d['minute_peak_knots'],round(time.monotonic()-t,1),len(done),flush=True)
   except Exception as e:
    with errs.open('a') as f:f.write(json.dumps({'station':sid,'year':y,'error':repr(e),'traceback':traceback.format_exc()[-1200:]})+'\n')
    print('ERROR',sid,y,repr(e),flush=True)
   time.sleep(1.05)
 (ROOT/'batch.exit.json').write_text(json.dumps({'done':len(done),'expected':len(SIDS)*24,'errors':sum(1 for _ in errs.open()) if errs.exists() else 0,'utc':fmt(dt.datetime.utcnow())}))
if __name__=='__main__':main()

"""Colab-only TURDATA full-period RAW intensity screen; checkpoint month by month."""
import os, re, time, json, math, csv, zipfile, datetime as dt, collections, requests
from pathlib import Path
ROOT=Path('/content/prague_qc'); ROOT.mkdir(exist_ok=True)
URL='https://zenodo.org/api/records/10655033/files/LIDAR_wind_profile_TURDATA.zip/content'
ZIP=ROOT/'lidar.zip'; SIZE=1963148669

def download():
    for attempt in range(20):
        offset=ZIP.stat().st_size if ZIP.exists() else 0
        if offset==SIZE:return
        try:
            r=requests.get(URL,headers={'Range':f'bytes={offset}-'} if offset else {},stream=True,timeout=(30,120))
            if r.status_code in (429,500,502,503,504):
                delay=min(300,15*2**min(attempt,4));print('HTTP',r.status_code,'wait',delay,flush=True);time.sleep(delay);continue
            r.raise_for_status()
            if offset and r.status_code!=206:raise RuntimeError('server ignored Range; preserve partial and stop')
            last=time.monotonic()
            with ZIP.open('ab') as f:
                for block in r.iter_content(2*1024*1024):
                    if block:f.write(block)
                    if time.monotonic()-last>45:
                        print('download MB',round(ZIP.stat().st_size/1e6,1),'/',SIZE/1e6,flush=True);last=time.monotonic()
            if ZIP.stat().st_size==SIZE:return
        except (requests.RequestException,TimeoutError) as e:
            print('retry',repr(e),'size',ZIP.stat().st_size if ZIP.exists() else 0,flush=True)
        time.sleep(min(300,15*2**min(attempt,4)))
    raise RuntimeError('download incomplete after retries')

def raw(b):
    rows=[];group=[]
    for line in b.decode('ascii','replace').splitlines():
        a=line.split()
        if len(a)==5 and a[0].isdigit():
            try:g=int(a[0]);v=float(a[2])
            except ValueError:continue
            if g==0 and group:rows.append(group);group=[]
            group.append((g,v))
    if group:rows.append(group)
    return [dict(r).get(32,float('nan')) for r in rows]

def speed(b):
    for line in b.decode('ascii','replace').splitlines()[1:]:
        a=line.split()
        if len(a)>=3:
            try:
                if abs(float(a[0])-101.4)<0.2:return float(a[2])
            except ValueError:pass
    return float('nan')

def screen():
    with zipfile.ZipFile(ZIP) as z:
        lookup=set(z.namelist())
        names=sorted(n for n in lookup if re.search(r'/Wind_Profile_188_2022(04|05|06|07|08|09)\d{2}_\d{6}\.hpl$',n))
        print('raw count',len(names),flush=True)
        for month in ('04','05','06','07','08','09'):
            target=ROOT/f'qc_2022{month}.json'
            if target.exists():print('skip complete',month,flush=True);continue
            by=collections.defaultdict(lambda:collections.defaultdict(list));count=collections.Counter();records=[]
            selected=[n for n in names if f'/Wind_Profile_188_2022{month}' in n]
            for i,n in enumerate(selected):
                p=n.replace('/Wind_Profile_','/Processed_Wind_Profile_')
                if p not in lookup:count['missing_processed']+=1;continue
                ts=dt.datetime.strptime(''.join(re.search(r'_(2022\d{4})_(\d{6})\.hpl$',n).groups()),'%Y%m%d%H%M%S')
                hour=(ts+dt.timedelta(minutes=25)).replace(minute=0,second=0,microsecond=0)
                rays=raw(z.read(n));u=speed(z.read(p));count['paired']+=1
                good=math.isfinite(u) and 0<=u<=40
                if not good:count['physical_reject']+=1
                for threshold in (1.010,1.015,1.020):
                    if good and sum(math.isfinite(v) and v>=threshold for v in rays)>=4:
                        by[str(threshold)][hour.isoformat()].append(u);count[f'profile_{threshold}']+=1
                        if threshold==1.015:records.append((ts.isoformat(),hour.isoformat(),u))
                if i%1000==0:print(month,i,'/',len(selected),flush=True)
            summary={t:{'hours_ge4':sum(len(v)>=4 for v in hours.values()),'profiles':sum(map(len,hours.values())),'mean_speed':sum(map(sum,hours.values()))/sum(map(len,hours.values())) if hours else None} for t,hours in by.items()}
            data={'month':f'2022-{month}','count':dict(count),'summary':summary,'records':records,'hours':{h:sum(v)/len(v) for h,v in by['1.015'].items() if len(v)>=4}}
            tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data));os.replace(tmp,target)
            print('MONTH_DONE',month,json.dumps(summary),flush=True)
if __name__=='__main__':
    download();print('DOWNLOAD_DONE',ZIP.stat().st_size,flush=True)
    screen();print('QC_DONE',flush=True)

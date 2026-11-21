"""Stream TURDATA RAW/processed ZIP members via byte range; no full archive download.
QC is a screening proxy, not a certified VAD retrieval QC. Usage: python run_qc.py [YYYYMMDD ...]
"""
import sys,zipfile,re,datetime as dt,collections,math,json,time,threading,concurrent.futures
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'data_survey_v1'))
from check_prague import Remote,URL

OUT=Path(__file__).resolve().parent
DAYS=set(sys.argv[1:])
THRESH=(1.010,1.015,1.020)

def raw_intensity(b):
    lines=b.decode('ascii','replace').splitlines()
    rows=[];group=[]
    for line in lines:
        a=line.split()
        if len(a)==5 and a[0].isdigit():
            try:g=int(a[0]); intensity=float(a[2])
            except ValueError:continue
            if g==0 and group:rows.append(group);group=[]
            group.append((g,intensity))
    if group:rows.append(group)
    # 18 m overlapping gates at 3 m steps; angle 75 deg from horizontal.
    # gate 32 nominal vertical height ~101.4 m from instrument.
    return [[d.get(32,float('nan')) for d in (dict(r) for r in rows)],len(rows)]

def proc_speed(b):
    for line in b.decode('ascii','replace').splitlines()[1:]:
        a=line.split()
        if len(a)>=3:
            try:
                if abs(float(a[0])-101.4)<0.2:return float(a[2])
            except ValueError:pass
    return float('nan')

start=time.time();out=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list)))
examples=[];total=collections.Counter(); local=threading.local();sessions=[]
def get_zip():
    if not hasattr(local,'zip'):
        src=Remote(URL);local.src=src;local.zip=zipfile.ZipFile(src)
        sessions.append(src)
    return local.zip

with zipfile.ZipFile(Remote(URL)) as directory:
    names=directory.namelist()
raw=[n for n in names if re.search(r'/Wind_Profile_188_2022(04|05|06|07|08|09)\d{2}_\d{6}\.hpl$',n) and (not DAYS or n.split('/')[1] in DAYS)]
print('raw members',len(raw),flush=True)

def one(n):
    z=get_zip();pn=n.replace('/Wind_Profile_','/Processed_Wind_Profile_')
    if pn not in z.NameToInfo:return None
    ts=dt.datetime.strptime(''.join(re.search(r'_(2022\d{4})_(\d{6})\.hpl$',n).groups()),'%Y%m%d%H%M%S')
    # File time = raw header start (within minutes), timezone not documented.
    hour=(ts+dt.timedelta(minutes=25)).replace(minute=0,second=0,microsecond=0)
    intens,nr=raw_intensity(z.read(n));speed=proc_speed(z.read(pn))
    good=math.isfinite(speed) and 0<=speed<=40
    passed=[str(t) for t in THRESH if good and sum(math.isfinite(v) and v>=t for v in intens)>=4]
    return (n,ts.strftime('%Y-%m'),hour.isoformat(),intens,nr,speed,good,passed)

with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for i,r in enumerate(pool.map(one,raw)):
        if r is None:continue
        n,month,hour,intens,nr,speed,good,passed=r
        if len(examples)<8:examples.append({'file':n,'rays':nr,'intensity_gate32':intens,'processed_speed':speed})
        total['paired']+=1
        if not good:total['physical_reject']+=1
        for t in passed:
            out[month][t][hour].append(speed);total[f'profile_{t}']+=1
        if i%3000==0:print('progress',i,'/',len(raw),'MB',round(sum(s.bytes for s in sessions)/1e6,1),'s',round(time.time()-start),flush=True)
summary={m:{t:{'hours_ge4':sum(len(v)>=4 for v in hours.values()),'profiles':sum(map(len,hours.values())),'mean_speed':round(sum(sum(v) for v in hours.values())/sum(map(len,hours.values())),3) if hours else None} for t,hours in by.items()} for m,by in out.items()}
result={'thresholds':THRESH,'criterion':'at least 4 of 6 RAW rays at nominal gate 32 pass intensity, processed speed 0..40 m/s, at least four profiles per centered hour; this proxy DOES NOT independently certify VAD R2 or UTC','examples':examples,'monthly':summary,'counts':dict(total),'range_bytes':sum(s.bytes for s in sessions),'elapsed_seconds':round(time.time()-start)}
(OUT/'qc_screen.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print('SUMMARY',json.dumps(result,ensure_ascii=False),flush=True)

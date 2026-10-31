"""Count Prague processed HPL profile hours from remote ZIP ranges (no whole ZIP)."""
from check_prague import Remote,URL
import zipfile,re,collections,math,datetime as dt,json,time
from pathlib import Path
out=Path(__file__).with_name('prague_coverage.json')
src=Remote(URL);months=collections.defaultdict(lambda:collections.defaultdict(dict));statistics=collections.Counter();progress={};t0=time.time()
with zipfile.ZipFile(src) as z:
    entries=sorted((x for x in z.infolist() if '/Processed_Wind_Profile_' in x.filename),key=lambda x:x.header_offset)
    for i,x in enumerate(entries):
        stamp=re.search(r'_(\d{8})_(\d{6})\.hpl$',x.filename)
        if not stamp:continue
        timestamp=dt.datetime.strptime(''.join(stamp.groups()),'%Y%m%d%H%M%S');month=timestamp.strftime('%Y-%m')
        if month<'2022-04' or month>'2022-10':continue
        b=z.read(x);statistics[(month,'profiles')]+=1
        # First line gate count. Remaining are height, direction, scalar speed. Values are processed, not independently QC-certified.
        gates={}
        for ln in b.decode('utf-8','replace').splitlines()[1:]:
            a=ln.split()
            if len(a)<3:continue
            try:h,d,s=map(float,a[:3])
            except ValueError:continue
            if 30<=h<=150 and abs(h-50)<1.5:gates[50]=(h,d,s)
            if 30<=h<=150 and abs(h-100)<1.5:gates[100]=(h,d,s)
            if 30<=h<=150 and abs(h-150)<2.5:gates[150]=(h,d,s)
        for gate,(_,direction,speed) in gates.items():
            if math.isfinite(speed) and speed>=0 and math.isfinite(direction) and 0<=direction<=360:
                # Centered hour; timestamp is assumed profile end time, 5-min shift. 33-min interpretation unverified.
                hour=(timestamp-dt.timedelta(minutes=5)+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
                months[month][gate].setdefault(hour,[]).append((direction,speed))
                statistics[(month,f'valid_profile_{gate}')]+=1
        if i%3500==0:print('PROGRESS',i,len(entries),'download_MB',round(src.bytes/1e6,1),'elapsed_s',round(time.time()-t0),flush=True)
    result=[]
    for m in sorted(set(x.filename[:4]+'-'+x.filename[4:6] for x in entries if re.match(r'\d{6}',x.filename))):
        for gate in (50,100,150):
            bins=months[m][gate];eligible=[v for v in bins.values() if len(v)>=4]
            # scalar speed and direction sanity, not formal QC
            speeds=[s for vals in eligible for d,s in vals]
            result.append({'month':m,'gate_target_agl':gate,'nearest_gate_agl':{50:49.3,100:101.4,150:147.8}[gate], 'profiles':statistics[(m,'profiles')], 'valid_profiles_at_gate':statistics[(m,f'valid_profile_{gate}')], 'hours_ge4':len(eligible),'mean_scalar_speed':round(sum(speeds)/len(speeds),3) if speeds else None,'max_scalar_speed':round(max(speeds),3) if speeds else None})
    out.write_text(json.dumps({'definition':'Processed HPL, file timestamp assumed end of profile; >=4 valid 50/100/150 m profile values in centered hour. Time zone and per-profile averaging duration not certified. No independent QC.', 'monthly':result,'bytes_fetched':src.bytes,'total_entries':len(entries)},indent=2))
    print('DONE',len(entries),'MB',round(src.bytes/1e6,1),'seconds',round(time.time()-t0),flush=True)

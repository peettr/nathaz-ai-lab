"""D2 text preparation. Input: WeatherBench v1 5.625° arrays, never targets.
Only the requested initialisation t and t-6h are read. Dates index arrays and
are not passed as predictors. No network, deletion or credentials.
"""
import argparse, datetime as dt, json, pathlib, random
import numpy as np

FIELDS=('z','t','t2m','u10','v10')
# Fixed latitude/longitude quadrants. Native WB grid: latitude 90..-84.375,
# longitude 0..354.375; sectors do not depend on the forecast date.
REGIONS={'north_west':(0,16,0,32),'north_east':(0,16,32,64),
         'south_west':(16,32,0,32),'south_east':(16,32,32,64)}
SEED=31026
PROMPT='''You are a scientific weather analyst. Convert the supplied STRUCTURED SUMMARY into one factual 60–120-word English synoptic description. Use only the supplied values and coordinates. Geopotential-height extrema are not surface pressure; call them upper-level height highs/lows. Do not infer a front, jet speed at an unprovided level, forecast future weather, calendar date, or other unprovided facts. Describe 850-hPa temperature gradients as gradient zones, and 10-m strong winds as 10-m winds. Describe regional departures relative to the given 1979–2015 regional training means. Do not add forecasts or speculation. Return only the paragraph, with no bullets.
STRUCTURED SUMMARY:
{summary_json}'''
TEMPLATE=('At initialization, 500-hPa geopotential-height maximum is {z_high} and minimum is {z_low}. '
          'The strongest 850-hPa temperature gradient is near {gradient}. '
          'The strongest 10-m wind region is {wind}. '
          'Regional 2-m temperature departures from 1979–2015 training-region means are {t_anomaly}. '
          'Relative to the previous six-hour input, regional mean 2-m temperature changes are {t_change}.')

def load_pair(root, timestamp):
    """Read strictly one time slice at t and t-6 h for every field."""
    arrays={}
    for label,instant in (('t',timestamp),('previous',timestamp-dt.timedelta(hours=6))):
        year=instant.year
        base=dt.datetime(year,1,1)
        index=int((instant-base).total_seconds()//21600)
        arrays[label]={f:np.asarray(np.load(root/f'{f}_{year}_6h.npy',mmap_mode='r')[index],dtype=np.float32)
                       for f in FIELDS}
        assert all(a.shape==(32,64) and np.isfinite(a).all() for a in arrays[label].values())
    return arrays

def regional_reference(root):
    """Only training years, never validation/test, future of initialization or test targets."""
    out={}
    for name,(a,b,c,d) in REGIONS.items():
        total=0.; n=0
        for y in range(1979,2016):
            ar=np.load(root/f't2m_{y}_6h.npy',mmap_mode='r')
            total+=float(np.asarray(ar[:,a:b,c:d],dtype=np.float64).sum());n+=ar.shape[0]*(b-a)*(d-c)
        out[name]=total/n
    return out

def coord(i,j):
    lat=90-5.625*i; lon=5.625*j
    return f'{lat:.3f}°N, {lon:.3f}°E'

def summary(x,refs):
    now=x['t']; prev=x['previous']; z=now['z']; temp=now['t']; t2=now['t2m']
    speed=np.hypot(now['u10'],now['v10'])
    hi=tuple(map(int,np.unravel_index(np.argmax(z),z.shape)))
    lo=tuple(map(int,np.unravel_index(np.argmin(z),z.shape)))
    # 850 hPa centered finite differences (K/degree), longitude periodic.
    dy=np.gradient(temp,5.625,axis=0)
    dx=(np.roll(temp,-1,axis=1)-np.roll(temp,1,axis=1))/11.25
    grad=np.hypot(dy,dx)
    gi=tuple(map(int,np.unravel_index(np.argmax(grad),grad.shape)))
    wi=tuple(map(int,np.unravel_index(np.argmax(speed),speed.shape)))
    regions={name:{'t2m_anomaly_K':round(float(t2[a:b,c:d].mean())-refs[name],2),
                   't2m_change_6h_K':round(float(t2[a:b,c:d].mean()-prev['t2m'][a:b,c:d].mean()),2),
                   'wind10_mean_m_s':round(float(speed[a:b,c:d].mean()),2)}
             for name,(a,b,c,d) in REGIONS.items()}
    return {'z500_max':{'location':coord(*hi),'m2_s2':round(float(z[hi]),2)},
            'z500_min':{'location':coord(*lo),'m2_s2':round(float(z[lo]),2)},
            't850_gradient_max':{'location':coord(*gi),'K_per_degree':round(float(grad[gi]),3)},
            'wind10_max':{'location':coord(*wi),'m_s':round(float(speed[wi]),2)},
            'regions':regions,'reference':'1979–2015 region mean; same fixed regions; t and t-6h only'}

def templ(s):
    anom='; '.join(f'{k} {v["t2m_anomaly_K"]:+.2f} K' for k,v in s['regions'].items())
    change='; '.join(f'{k} {v["t2m_change_6h_K"]:+.2f} K' for k,v in s['regions'].items())
    return TEMPLATE.format(z_high=f'{s["z500_max"]["location"]} ({s["z500_max"]["m2_s2"]} m²/s²)',
                           z_low=f'{s["z500_min"]["location"]} ({s["z500_min"]["m2_s2"]} m²/s²)',
                           gradient=f'{s["t850_gradient_max"]["location"]} ({s["t850_gradient_max"]["K_per_degree"]} K/degree)',
                           wind=f'{s["wind10_max"]["location"]} ({s["wind10_max"]["m_s"]} m/s)',
                           t_anomaly=anom,t_change=change)

def sample_dates():
    # Date is used only to index input fields, never included in the LLM prompt.
    return [dt.datetime(2017,m,15,12) for m in (1,2,3,4,5,6,7,8,9,10)]

def mismatch_map(dates,seed=SEED):
    # Fixed derangement, one-to-one, no sample ever receives its own date.
    # A nonzero cyclic displacement of a shuffled index gives a permutation.
    rng=random.Random(seed); order=list(range(len(dates)));rng.shuffle(order)
    displacement=rng.randrange(1,len(dates))
    return {dates[order[i]].isoformat():dates[order[(i+displacement)%len(dates)]].isoformat()
            for i in range(len(dates))}

def all_dates():
    start=dt.datetime(1979,1,1);end=dt.datetime(2019,1,1)
    return [start+dt.timedelta(hours=6*i) for i in range(int((end-start).total_seconds()//21600))]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=pathlib.Path,required=True);ap.add_argument('--out',type=pathlib.Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    refs=regional_reference(args.root); dates=sample_dates();rows=[]
    for d in dates:
        s=summary(load_pair(args.root,d),refs)
        rows.append({'initialization':d.isoformat(),'input_only':['t','t-6h'],
                     'summary':s,'template':templ(s),'prompt':PROMPT.format(summary_json=json.dumps(s,ensure_ascii=False,sort_keys=True))})
    (args.out/'samples_pre_llm.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    full_dates=all_dates();mapping=mismatch_map(full_dates)
    assert len(mapping)==len(full_dates) and len(set(mapping.values()))==len(full_dates)
    assert all(k!=v for k,v in mapping.items())
    (args.out/'mismatch_all_dates.json').write_text(json.dumps(mapping,indent=2))
    (args.out/'regional_reference.json').write_text(json.dumps(refs,indent=2))
    print('PREP_DONE',len(rows),flush=True)
if __name__=='__main__': main()

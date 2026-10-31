"""L26.12 pilot: frozen IBTrACS cohort and first 50 Pangu activations on Colab A100."""
import csv, hashlib, json, os, subprocess, sys, time, traceback, urllib.request
from pathlib import Path
T0=time.time(); ROOT=Path('/content/l2612'); ROOT.mkdir(exist_ok=True)
def event(**kw):
    kw['wall_s']=round(time.time()-T0,2)
    with (ROOT/'progress.jsonl').open('a') as f: f.write(json.dumps(kw,default=str)+'\n')
    print(json.dumps(kw,default=str),flush=True)
def finish(state, **kw):
    event(stage=state,**kw)
    (ROOT/'pilot.done').write_text(state+'\n')
try:
    subprocess.run([sys.executable,'-m','pip','install','-q','onnx','onnxruntime-gpu','xarray','zarr<3','gcsfs','pandas','scipy'],check=True)
    import numpy as np, onnx, onnxruntime as ort, xarray as xr
    from onnx import helper
    event(stage='deps',ort=ort.__version__,providers=ort.get_available_providers())
    csvs=[]
    base='https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/'
    for basin in ('NA','WP'):
        name=f'ibtracs.{basin}.list.v04r01.csv'; path=ROOT/name
        urllib.request.urlretrieve(base+name,path)
        csvs.append(path); event(stage='csv',name=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    storms={}
    for path in csvs:
        with path.open(newline='') as f:
            reader=csv.DictReader(f)
            for row in reader:
                sid=row['SID'].strip(); iso=row['ISO_TIME'].strip()
                if not sid or not iso or not iso[:4].isdigit(): continue
                yr=int(iso[:4]);
                if yr<2015 or yr>2022 or iso[-8:] not in ('00:00:00','06:00:00','12:00:00','18:00:00'): continue
                def number(*names):
                    for name in names:
                        try: return float(row[name])
                        except (ValueError,KeyError,TypeError): pass
                    return None
                wind=number('USA_WIND','WMO_WIND'); lat=number('LAT'); lon=number('LON')
                if wind is None or wind<34 or lat is None or lon is None: continue
                rec={'sid':sid,'time':iso,'year':yr,'basin':path.name.split('.')[1], 'lat':lat,'lon':lon,'wind_kt':wind,'pres_hpa':number('USA_PRES','WMO_PRES'),'rmw_nm':number('USA_RMW')}
                storms.setdefault(sid,{})[iso]=rec
    from datetime import datetime
    chosen=[]
    for sid, times in sorted(storms.items()):
        records=list(times.values()); years={r['year'] for r in records}
        # A storm spanning the train/test boundary is excluded in full.
        if any(y<=2020 for y in years) and any(y>=2021 for y in years): continue
        records.sort(key=lambda r:(-r['wind_kt'],r['time']))
        taken=[]
        for r in records:
            t=datetime.fromisoformat(r['time'])
            if all(abs((t-datetime.fromisoformat(x['time'])).total_seconds())>=86400 for x in taken): taken.append(r)
            if len(taken)==4: break
        chosen+=taken
    chosen.sort(key=lambda r:(r['year']>=2021,r['sid'],r['time']))
    census={'train_storms':len({r['sid'] for r in chosen if r['year']<=2020}),'test_storms':len({r['sid'] for r in chosen if r['year']>=2021}),'train_times':sum(r['year']<=2020 for r in chosen),'test_times':sum(r['year']>=2021 for r in chosen),'years':[2015,2022],'selection':'up to four intensity-prioritized 6-hourly >=34kt records per SID separated >=24h; cross-boundary SID excluded'}
    (ROOT/'manifest.json').write_text(json.dumps({'census':census,'records':chosen},indent=1))
    event(stage='census',**census)
    if census['test_storms']<30:
        finish('insufficient_test_storms',**census); sys.exit(0)
    W=ROOT/'pangu_weather_24.onnx'; URL='https://sites.ecmwf.int/repository/ai-models/test-data/pangu-weather/pangu_weather_24.onnx'
    urllib.request.urlretrieve(URL,W)
    digest=hashlib.file_digest(W.open('rb'),'sha256').hexdigest()
    assert digest=='613a5c140a1399abcaffb4dbce32af373a1f5f56c515704f5be61925bb9fdcfd',digest
    event(stage='weights',bytes=W.stat().st_size,sha256=digest)
    ds=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr',storage_options={'token':'anon'},chunks=None)
    levs=[1000,925,850,700,600,500,400,300,250,200,150,100,50]
    def grab(rec):
        s=ds.sel(time=np.datetime64(rec['time']))
        up=np.stack([s[v].sel(level=levs).values for v in ['geopotential','specific_humidity','temperature','u_component_of_wind','v_component_of_wind']]).astype(np.float32)
        sf=np.stack([s[v].values for v in ['mean_sea_level_pressure','10m_u_component_of_wind','10m_v_component_of_wind','2m_temperature']]).astype(np.float32)
        lat=s['latitude'].values
        if lat[0]<lat[-1]:up=up[...,::-1,:];sf=sf[...,::-1,:]
        assert up.shape==(5,13,721,1440) and sf.shape==(4,721,1440)
        return np.ascontiguousarray(up),np.ascontiguousarray(sf)
    m=onnx.load(str(W)); nodes=list(m.graph.node); k=3856
    producer={o:i for i,n in enumerate(nodes) for o in n.output}
    ini={i.name for i in m.graph.initializer}
    boundary=sorted({x for n in nodes[k:] for x in n.input if x and x not in ini and producer.get(x,-1)<k})
    a=onnx.load(str(W)); del a.graph.output[:]
    a.graph.output.extend([helper.make_tensor_value_info(x,onnx.TensorProto.FLOAT,None) for x in boundary])
    opts=ort.SessionOptions();opts.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    sess=ort.InferenceSession(a.SerializeToString(),opts,providers=['CUDAExecutionProvider','CPUExecutionProvider'])
    main='/b1/Add_26_output_0'
    assert main in boundary and any(i.name==main for i in sess.get_outputs())
    event(stage='segment_ready',boundary=boundary,provider=sess.get_providers())
    def indices(rec):
        # Hypothesis: eight blocks, 91 x 180 tokens, 2 degree-ish centers.
        yy=np.arange(91);xx=np.arange(180)
        rows=np.where(np.abs(90-2*yy-rec['lat'])<=5)[0]
        dlon=(2*xx-rec['lon']+180)%360-180
        cols=np.where(abs(dlon)<=5)[0]
        return np.array([b*91*180+y*180+x for b in range(8) for y in rows for x in cols],dtype=np.int64)
    selected=chosen[:50]
    for n,r in enumerate(selected):
        up,sf=grab(r)
        t1=time.time()
        values=sess.run([main],{'input':up,'input_surface':sf})[0][0]
        idx=indices(r)
        assert values.shape==(131040,384) and len(idx)>0
        f=ROOT/f'activation_{n:04d}.npz'
        np.savez_compressed(f,window=values[idx].astype(np.float16),indices=idx.astype(np.int32))
        del up,sf,values
        event(stage='activation',n=n+1,requested=50,sid=r['sid'],time=r['time'],file=f.name,bytes=f.stat().st_size,token_count=[已隐去],step_s=round(time.time()-t1,2))
    finish('pilot50_complete',**census)
except BaseException as exc:
    event(stage='error',error=repr(exc),traceback=traceback.format_exc())
    (ROOT/'pilot.done').write_text('error\n')
    raise

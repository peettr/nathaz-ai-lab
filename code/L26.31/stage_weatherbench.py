"""Stage exact WeatherBench v1 5.625-degree yearly NetCDF to six-hour arrays on Colab.
No project data is stored on 工作站. Only public data URLs, no credentials.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import urllib.parse
import urllib.request
import zipfile

import netCDF4
import numpy as np

ROOT = pathlib.Path('/content/l2631/weatherbench')
ROOT.mkdir(parents=True, exist_ok=True)
BASE = 'https://dataserv.ub.tum.de/index.php/s/m1524895/download'
VARIABLES = {
    'geopotential_500': 'z', 'temperature_850': 't',
    '2m_temperature': 't2m', '10m_u_component_of_wind': 'u10',
    '10m_v_component_of_wind': 'v10',
}

def fetch(url, dest):
    if dest.exists():
        assert dest.stat().st_size > 1000, dest
        print('reuse existing download', dest, flush=True)
        return
    partial = dest.with_suffix(dest.suffix + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'L26.31-WeatherBench-research/1'})
    with urllib.request.urlopen(request, timeout=60) as response, open(partial, 'xb') as out:
        expected = response.headers.get('Content-Length')
        n = 0
        while True:
            block = response.read(4 * 1024 * 1024)
            if not block: break
            out.write(block); n += len(block)
            if n // (256*1024*1024) != (n-len(block)) // (256*1024*1024):
                print(dest.name, 'download MB', round(n/1e6), flush=True)
        if expected: assert n == int(expected), (n, expected)
    partial.rename(dest)
    print('download complete', dest.name, n, flush=True)

manifest = {}
for directory, field in VARIABLES.items():
    filename = directory + '_5.625deg.zip'
    url = BASE + '?' + urllib.parse.urlencode({'path':'/5.625deg/'+directory, 'files':filename})
    archive = ROOT / filename
    fetch(url, archive)
    h = hashlib.sha256()
    with open(archive,'rb') as fd:
        for block in iter(lambda:fd.read(4*1024*1024), b''): h.update(block)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        expected_years = set(range(1979,2019))
        yearly = {}
        for name in names:
            if name.endswith('.nc') and any(f'_{y}_5.625deg.nc' in name for y in expected_years):
                assert not name.startswith('/') and '..' not in pathlib.PurePosixPath(name).parts
                yr = int(name.split('_')[-2]); assert yr not in yearly
                yearly[yr] = name
        assert set(yearly)==expected_years, (directory, sorted(set(expected_years)-set(yearly)))
        for yr, name in sorted(yearly.items()):
            dest = ROOT / f'{field}_{yr}_6h.npy'
            if dest.exists():
                a=np.load(dest,mmap_mode='r'); assert a.shape[1:] == (32,64) and a.shape[0] in (1460,1464)
                continue
            with z.open(name) as stream:
                raw=stream.read()
            nc=netCDF4.Dataset('inmemory',memory=raw)
            choices = [k for k,v in nc.variables.items() if v.ndim==3 and tuple(v.shape[1:])==(32,64)]
            assert len(choices)==1,(name,choices)
            v=nc.variables[choices[0]]
            hours=len(v)
            assert hours in (8760,8784),(name,hours)
            times=netCDF4.num2date(nc.variables['time'][[0,6,-1]],nc.variables['time'].units,
                                   calendar=getattr(nc.variables['time'],'calendar','standard'))
            assert (times[0].year,times[0].month,times[0].day,times[0].hour)==(yr,1,1,0), (name,times)
            assert times[1].hour == 6 and times[-1].year == yr, (name,times)
            a=np.asarray(v[::6],dtype=np.float32)
            assert a.shape == (hours//6,32,64) and np.isfinite(a).all(),(name,a.shape)
            np.save(dest,a,allow_pickle=False)
            nc.close(); del raw,a
            print('extracted',directory,yr,'samples',hours//6,flush=True)
    manifest[directory]={'url':url,'zip_sha256':h.hexdigest(),'years':sorted(yearly),'field':field}
    (ROOT/'stage_manifest.json').write_text(json.dumps(manifest,indent=2))
url=BASE+'?'+urllib.parse.urlencode({'path':'/5.625deg/constants','files':'constants_5.625deg.nc'})
fetch(url,ROOT/'constants_5.625deg.nc')
nc=netCDF4.Dataset(str(ROOT/'constants_5.625deg.nc'))
print('constants variables',[(k,tuple(v.shape)) for k,v in nc.variables.items()],flush=True)
nc.close()
(ROOT/'stage.done').write_text(dt.datetime.now(dt.timezone.utc).isoformat())
print('STAGE_DONE',ROOT,flush=True)

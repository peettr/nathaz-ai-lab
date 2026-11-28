#!/usr/bin/env python3
"""One-time independent OSDF download and masked-point comparison; never alter source."""
import hashlib, json, pathlib, urllib.request
import numpy as np
import pygrib
root=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_R1R2_v1')
original=root/'raw/2024073100/gfs.0p25b.2024073100.f000.grib2'
new=root/'raw/2024073100/gfs.0p25b.2024073100.f000.grib2.redownload_v3'
report=root/'SOURCE_COMPARE_225GH_2024073100_v3.json'
url='https://osdf-director.osg-htc.org/ncar/gdex/d084003/2024/20240731/gfs.0p25b.2024073100.f000.grib2'
assert original.is_file() and not new.exists() and not report.exists()
req=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(req,timeout=120) as resp: expected=int(resp.headers['Content-Length']);assert resp.status==200
assert original.stat().st_size==expected
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=200) as resp,new.open('xb') as out:
    assert resp.status==200
    while chunk:=resp.read(4*1024*1024):out.write(chunk)
assert new.stat().st_size==expected and new.open('rb').read(4)==b'GRIB'
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def mask(p):
    with pygrib.open(str(p)) as grbs:
        msg=grbs.select(shortName='gh',typeOfLevel='isobaricInhPa',level=225)
        assert len(msg)==1
        v=msg[0].values
        m=~np.isfinite(np.ma.filled(v,np.nan))
        return np.argwhere(m),m
old_idx,oldmask=mask(original);new_idx,newmask=mask(new)
result={'url':url,'http_head':200,'expected_bytes':expected,'original':str(original),'redownload':str(new),'original_sha256':digest(original),'redownload_sha256':digest(new),'old_nonfinite':len(old_idx),'new_nonfinite':len(new_idx),'identical_mask':bool(np.array_equal(oldmask,newmask)),'old_indices_ij':old_idx.tolist(),'new_indices_ij':new_idx.tolist()}
report.write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if not k.endswith('_ij')},indent=2),flush=True)

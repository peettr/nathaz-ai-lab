#!/usr/bin/env python3
"""Fetch official immutable checkpoint and normalization statistics into new probe root."""
import hashlib, pathlib, urllib.request, urllib.parse
root=pathlib.Path(__file__).resolve().parent/'weights'
files={
'params/GraphCast - ERA5 1979-2017 - resolution 0.25 - pressure levels 37 - mesh 2to6 - precipitation input and output.npz':'4e8cf600f3f402ebb430483e782b94648cef57bb757dec24dd7b11760d3fbacc',
'stats/diffs_stddev_by_level.nc':'e688fc51fe72e1dc897678ef5ce9889add64e28e13f3cec4758d8e47d429c1ce',
'stats/mean_by_level.nc':'e6e724b94cd27707903cdc5cf5784d420bab306f722e631f4455e25c96da9931',
'stats/stddev_by_level.nc':'29f941d8c34906b87a1745f93b2308d1e169ec9bbdc4c5491479c771fe92c3cb'}
for stem, expected in files.items():
    path=root/stem;path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        url='https://storage.googleapis.com/dm_graphcast/graphcast/'+urllib.parse.quote(stem)
        urllib.request.urlretrieve(url,path)
    with path.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual==expected,(stem,actual)
    print('WEIGHT_OK',stem,path.stat().st_size,actual,flush=True)

import urllib.request,urllib.parse,pathlib,hashlib,time
r=pathlib.Path('/content/r234c_gc37_v2/weights');(r/'params').mkdir(parents=True,exist_ok=True);(r/'stats').mkdir(exist_ok=True)
for stem in ['params/GraphCast - ERA5 1979-2017 - resolution 0.25 - pressure levels 37 - mesh 2to6 - precipitation input and output.npz','stats/diffs_stddev_by_level.nc','stats/mean_by_level.nc','stats/stddev_by_level.nc']:
 dest=r/stem;u='https://storage.googleapis.com/dm_graphcast/graphcast/'+urllib.parse.quote(stem)
 t=time.monotonic();urllib.request.urlretrieve(u,dest);print('WEIGHT',stem,dest.stat().st_size,hashlib.file_digest(dest.open('rb'),'sha256').hexdigest(),round(time.monotonic()-t,2),flush=True)

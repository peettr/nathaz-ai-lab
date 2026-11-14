import subprocess,sys,pathlib,hashlib,time,json,traceback,os
R=pathlib.Path('/content/l2612-input');R.mkdir(exist_ok=True)
LOG=pathlib.Path('/content/l2612-step3/stage.log');LOG.parent.mkdir(exist_ok=True)
def log(x):
 with LOG.open('a') as f:f.write(f'{time.time()} {x}\n')
 print(x,flush=True)
try:
 subprocess.run([sys.executable,'-m','pip','install','-q','onnx','onnxruntime-gpu','xarray','zarr<3','gcsfs'],check=True);log('install complete')
 files={
 'pangu_weather_24.onnx':'https://sites.ecmwf.int/repository/ai-models/test-data/pangu-weather/pangu_weather_24.onnx',
 'ibtracs.NA.list.v04r01.csv':'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NA.list.v04r01.csv',
 'ibtracs.WP.list.v04r01.csv':'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv'}
 for name,url in files.items():
  dest=R/name
  if not dest.exists():
   subprocess.run(['wget','-q','-O',str(dest),url],check=True)
  assert dest.stat().st_size>100000,name
  log(f'{name} {dest.stat().st_size} {hashlib.sha256(dest.read_bytes()).hexdigest()}')
 (LOG.parent/'stage.done').write_text('ok\n')
except BaseException:
 log(traceback.format_exc());(LOG.parent/'stage.done').write_text('error\n');raise

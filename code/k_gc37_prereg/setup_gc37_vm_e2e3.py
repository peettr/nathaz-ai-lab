import subprocess,sys,os,importlib,datetime
print('setup start',datetime.datetime.now().isoformat(),flush=True)
cmds=[['git','clone','--depth','1','https://github.com/NOAA-EMC/graphcast.git','/content/r234c_graphcast_source'],[sys.executable,'-m','pip','install','-q','pygrib','netcdf4','dask','dm-haiku','chex','jraph','rtree','trimesh','dm-tree','dinosaur-dycore','boto3','xarray','xarray-tensorstore']]
for cmd in cmds:
 print('RUN',cmd,flush=True)
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=500)
 print(p.stdout[-4500:],flush=True)
 if p.returncode: raise RuntimeError((cmd,p.returncode))
print('SETUP_DONE',datetime.datetime.now().isoformat(),flush=True)

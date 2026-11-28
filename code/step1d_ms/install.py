import subprocess,time,pathlib,sys
p=pathlib.Path('/content/step1d'); p.mkdir(exist_ok=True)
log=open(p/'install.log','w',buffering=1)
def run(cmd):
 print('RUN',cmd,flush=True,file=log); r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT); print('RC',r.returncode,flush=True,file=log); r.check_returncode()
try:
 run(['uv','python','install','3.12'])
 run(['uv','venv','--python','3.12','/content/step1d/venv'])
 run(['uv','pip','install','--python','/content/step1d/venv/bin/python','git+https://github.com/NHERI-SimCenter/BrailsPlusPlus.git@3369ee4dbdda','trimesh','rasterio','matplotlib'])
 print('DONE',file=log,flush=True)
except Exception as e:
 print('ERROR',repr(e),file=log,flush=True); raise
finally:log.close()

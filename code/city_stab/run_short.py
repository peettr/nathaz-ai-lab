"""Colab-only short stability test, with immutable output root."""
from pathlib import Path
import tarfile,subprocess,os,traceback,time,shutil
R=Path('/content/luw_citystab_short_v2');R.mkdir(exist_ok=False)
try:
 with tarfile.open('/content/city_monitor_inputs.tar.gz') as t:t.extractall(R,filter='data')
 src=R/'FluidX3D';case=R/'case'
 p=src/'src/defines.hpp';s=p.read_text();assert '//#define GROUND_WALL_MODEL' in s and '//#define CITY_STABILITY_MONITOR' in s
 p.write_text(s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL').replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 conf=(case/'conf.luwpf').read_text().replace('run_nstep = 31000','run_nstep = 8000').replace('purge_avg = 20000','purge_avg = 0');(case/'conf.luwpf').write_text(conf)
 with (R/'build.log').open('w') as f:c=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 print('BUILD',c.returncode,flush=True);assert c.returncode==0,(R/'build.log').read_text()[-2500:]
 env=os.environ.copy();env['LUW_GROUND_MIX_A']='0.0';env['OPENCL_VENDOR_PATH']='/etc/OpenCL/vendors'
 with (R/'solver.log').open('w',buffering=1) as f:c=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=1500)
 (R/'exit.txt').write_text(str(c.returncode));print('SOLVE',c.returncode,flush=True)
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());print('ERROR',traceback.format_exc()[-2500:],flush=True)
finally:
 (R/'short.done').write_text('terminal')

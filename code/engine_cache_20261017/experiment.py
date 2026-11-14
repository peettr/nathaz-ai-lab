import os,sys,time,json,hashlib,shutil,subprocess,traceback
from pathlib import Path
R=Path('/content/cache_run'); R.mkdir(exist_ok=True)
T={}
def log(s):
 msg=f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {s}'
 print(msg,flush=True)
 with open(R/'experiment.log','a') as f:f.write(msg+'\n')
def step(label,fn):
 t=time.monotonic();log('START '+label)
 try: return fn()
 finally:
  T[label]=round(time.monotonic()-t,2)
  (R/'times.json').write_text(json.dumps(T,indent=2))
  log(f'END {label} {T[label]}s')
def setup():
 args=['python3','setup.py','--family','unsloth','--model','UD-IQ4_XS','--context','32768','--vision','none','--host','127.0.0.1','--port','8090','--no-browser','--yes','--no-start']
 with open(R/'setup.log','w',buffering=1) as f:
  p=subprocess.Popen(args,cwd='/content/Strata',stdout=f,stderr=subprocess.STDOUT)
  last=''; prev=0
  while p.poll() is None:
   time.sleep(10)
   lines=Path(R/'setup.log').read_text(errors='replace').splitlines()
   for line in lines[prev:]:
    if any(x in line.lower() for x in ('engine already built','compiling','engine compiled','step 4','step 5','step 6','mtp','pack','error','failed')):log('SETUP '+line[:240])
   prev=len(lines)
   log(f'SETUP heartbeat {time.monotonic():.0f} log_lines={prev}')
  log('SETUP exit '+str(p.returncode))
  if p.returncode:raise RuntimeError('setup failed')
try:
 log('Begin pinned git '+subprocess.check_output(['git','-C','/content/Strata','rev-parse','HEAD'],text=True).strip())
 assert subprocess.check_output(['git','-C','/content/Strata','rev-parse','HEAD'],text=True).strip()=='477ac13cbe8e582c20484871ce459d20d82df09d'
 src=Path('/content/strata-v0.1.45-sm120'); dst=Path('/content/Strata/engine/strata');dst.parent.mkdir(exist_ok=True)
 def install():
  h=hashlib.file_digest(open(src,'rb'),'sha256').hexdigest()
  assert h=='08ce18d087a54d322bf293bea684aca5bb20c8cdb3a8306ca575bfad952635c8',h
  shutil.copy2(src,dst);dst.chmod(0o755)
  log(f'Installed cached binary bytes={dst.stat().st_size}, sha256={h}, BUILD.json present={(dst.parent/"BUILD.json").exists()}')
 step('binary_install',install)
 sys.path.insert(0,str(R));import runner
 step('hf_download_verify',runner.step2_download_weights)
 step('setup',setup)
 cfg=list(Path('/content/Strata').glob('strata-*.json'))
 log('configs '+str([p.name for p in cfg]))
 (R/'experiment.done').write_text(json.dumps(T))
except BaseException:
 log('ERROR '+traceback.format_exc());(R/'experiment.fail').write_text(json.dumps(T))

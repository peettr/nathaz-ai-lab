import os, time, json, hashlib, subprocess, sys, traceback
from pathlib import Path
R=Path('/content/final_cache'); R.mkdir(exist_ok=True)
T={}; BASE='gdrive:colab_cache/strata_v0.1.45_g4'
def log(x):
 s=f'{time.strftime("%Y-%m-%d %H:%M:%S")} {x}'
 print(s,flush=True)
 with (R/'stage_a.log').open('a') as f:f.write(s+'\n')
def run(args, cwd=None, timeout=None, quiet=False):
 t=time.monotonic();log('START '+ ' '.join(args))
 with (R/'command.log').open('a') as f:
  p=subprocess.Popen(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  while p.poll() is None:
   if timeout and time.monotonic()-t>timeout:
    p.terminate();p.wait(timeout=15);raise TimeoutError(args[0])
   log('HEARTBEAT '+args[0]+' '+str(round(time.monotonic()-t))+'s');time.sleep(20)
  p.wait()
 log(f'END {args[0]} rc={p.returncode} elapsed={time.monotonic()-t:.2f}s')
 if p.returncode:raise RuntimeError(f'{args[0]} failed rc={p.returncode}, inspect command.log')
 return round(time.monotonic()-t,2)
def measure(name,fn):
 t=time.monotonic();log('STAGE '+name)
 try:return fn()
 finally:
  T[name]=round(time.monotonic()-t,2);(R/'timings_a.json').write_text(json.dumps(T,indent=2));log(f'STAGE_END {name} {T[name]}s')
def checksum(path):
 h=hashlib.md5()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(32<<20),b''):h.update(b)
 return h.hexdigest()
def upload(path,dest):
 path=Path(path); assert path.exists(),path
 sec=run(['rclone','copyto',str(path),dest,'--transfers','1','--checkers','2','--drive-chunk-size','64M','--tpslimit','5','--retries','2','--low-level-retries','5','--stats','30s','--stats-one-line'],timeout=750)
 remote=subprocess.check_output(['rclone','lsjson','--stat',dest],text=True)
 j=json.loads(remote); assert j['Size']==path.stat().st_size,(dest,j['Size'],path.stat().st_size)
 md5=checksum(path); got=subprocess.check_output(['rclone','md5sum',dest],text=True).split()[0]
 assert md5==got,(dest,md5,got)
 with (R/'manifest.jsonl').open('a') as f:f.write(json.dumps({'local':str(path),'remote':dest,'size':path.stat().st_size,'md5':md5,'upload_s':sec})+'\n')
 log(f'VERIFIED {dest} bytes={path.stat().st_size} upload_s={sec} md5={md5}')
def main():
 run(['apt-get','update','-qq'],timeout=150)
 run(['apt-get','install','-y','-qq','aria2','ninja-build','cmake'],timeout=250)
 run([sys.executable,'-m','pip','install','-q','cmake','ninja','psutil','requests','urllib3'],timeout=180)
 run(['git','clone','-q','https://github.com/Niko1221/Strata.git','/content/Strata'],timeout=120)
 run(['git','-C','/content/Strata','checkout','-q','v0.1.45'],timeout=40)
 sha=subprocess.check_output(['git','-C','/content/Strata','rev-parse','HEAD'],text=True).strip()
 assert sha=='477ac13cbe8e582c20484871ce459d20d82df09d',sha
 log('PINNED '+sha)
 sys.path.insert(0,str(R));import runner
 measure('hf_download_verify',runner.step2_download_weights)
 def setup():
  run(['python3','setup.py','--family','unsloth','--model','UD-IQ4_XS','--context','32768','--vision','none','--host','127.0.0.1','--port','8090','--no-browser','--yes','--no-start','--gguf-dir','/content/Strata-data/models'],cwd='/content/Strata',timeout=1700)
 measure('setup',setup)
 engine=Path('/content/Strata/engine')
 assert (engine/'BUILD.json').exists() and (engine/'strata').exists()
 log('ENGINE_BUILD '+(engine/'BUILD.json').read_text()[:2000])
 (R/'engine_files.json').write_text(json.dumps([{'path':str(p),'size':p.stat().st_size} for p in engine.rglob('*') if p.is_file()],indent=2))
 log('DATA_INVENTORY '+json.dumps([{'path':str(p),'size':p.stat().st_size} for p in Path('/content/Strata-data').rglob('*') if p.is_file() and (p.stat().st_size>100_000_000 or 'mtp' in str(p).lower())][:50]))
 def cache():
  for p in engine.rglob('*'):
   if p.is_file() and p.stat().st_size<190_000_000: upload(p,BASE+'/engine/'+str(p.relative_to(engine)))
  for p in Path('/content/Strata').glob('strata-*.json'):upload(p,BASE+'/config/'+p.name)
  data=Path('/content/Strata-data')
  for root in ['packs','mtp']:
   for p in sorted((data/root).rglob('*')):
    if p.is_file():upload(p,BASE+'/data/'+str(p.relative_to(data)))
 measure('upload_cache',cache)
 (R/'stage_a.done').write_text(json.dumps(T))
 log('SUCCESS')
try:main()
except BaseException:
 log('ERROR '+traceback.format_exc());(R/'stage_a.fail').write_text(json.dumps(T))
finally:
 Path('/root/.config/rclone/rclone.conf').unlink(missing_ok=True)
 log('CONFIG_REMOVED '+str(not Path('/root/.config/rclone/rclone.conf').exists()))

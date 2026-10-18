import os,sys,time,subprocess,traceback,json,hashlib
from pathlib import Path
R=Path('/content/drive_stage'); R.mkdir(exist_ok=True)
START=time.time()
def log(s):
 print(time.strftime('%Y-%m-%d %H:%M:%S'),s,flush=True)
def cmd(args,timeout=None,env=None):
 log('START '+ ' '.join(args).replace('/root/.config/rclone/rclone.conf','[rclone config]'))
 t=time.time(); p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env=env)
 for line in p.stdout:
  # Never emit config contents or credential material, even on an unexpected error.
  if any(x in line.lower() for x in ('token','client_secret','authorization','refresh_token','access_token')):continue
  print(line.rstrip(),flush=True)
 rc=p.wait();log(f'END rc={rc} elapsed={time.time()-t:.1f}s')
 if rc:raise RuntimeError('subprocess failed, rc='+str(rc))
 return time.time()-t
try:
 log('stage begin')
 # Pin verified public sources and write no private configuration into logs.
 cmd(['apt-get','update','-qq']);cmd(['apt-get','install','-y','-qq','aria2','ninja-build','cmake','rclone'])
 cmd([sys.executable,'-m','pip','install','-q','cmake','ninja','psutil','requests','urllib3'])
 cmd(['git','clone','-q','https://github.com/Niko1221/Strata.git','/content/Strata'])
 cmd(['git','-C','/content/Strata','checkout','-q','v0.1.45'])
 sha=subprocess.check_output(['git','-C','/content/Strata','rev-parse','HEAD'],text=True).strip()
 assert sha=='477ac13cbe8e582c20484871ce459d20d82df09d',sha
 log('Strata SHA '+sha)
 sys.path.insert(0,'/content/drive_stage')
 import runner
 t=time.time();runner.step2_download_weights();log(f'HF weights measured={time.time()-t:.1f}s')
 t=time.time();runner.step3_run_setup();log(f'setup measured={time.time()-t:.1f}s')
 # Must retain unpacked weight shards, packed model, auxiliary layers and engine config.
 for p in sorted(Path('/content/Strata-data').rglob('*')):
  if p.is_file() and p.stat().st_size>100_000_000:log('large '+str(p.relative_to('/content/Strata-data'))+' '+str(p.stat().st_size))
 configs=list(Path('/content/Strata').glob('strata-*.json'))
 assert configs,'missing config'
 assert Path('/content/Strata/engine/strata').exists()
 log('config names '+','.join(p.name for p in configs))
 remote='gdcache:colab_cache/strata_v0.1.45_g4'
 flags=['--transfers','4','--checkers','4','--drive-chunk-size','64M','--stats','30s','--stats-one-line','--log-level','NOTICE']
 # First cache the small engine/config and the pack; avoid HF shards if Drive is slower.
 t=time.time()
 cmd(['rclone','copy','/content/Strata/engine/strata',remote+'/engine']+flags)
 for p in configs:cmd(['rclone','copy',str(p),remote+'/configs']+flags)
 log(f'engine and config upload={time.time()-t:.1f}s')
 pack=Path('/content/Strata-data/packs')
 assert pack.exists()
 t=time.time();cmd(['rclone','copy',str(pack),remote+'/packs']+flags);log(f'pack upload={time.time()-t:.1f}s')
 # Auxiliary MTP files can be outside packs; cache the complete data tree minus models/packs.
 t=time.time();cmd(['rclone','copy','/content/Strata-data',remote+'/data-other','--exclude','/models/**','--exclude','/packs/**']+flags);log(f'other data upload={time.time()-t:.1f}s')
 # The 94 GB original shards may be slower over Drive than HF; measure and cap stage cost.
 log('stage complete before optional weights upload; hold session for decision')
 (R/'stage.done').write_text(json.dumps({'stage_sec':time.time()-START,'sha':sha,'remote':remote}))
except BaseException:
 log('ERROR '+traceback.format_exc())
 (R/'stage.exit').write_text('failed '+str(time.time()))
finally:
 # Credentials must not survive a stage, even if the upload fails.
 Path('/root/.config/rclone/rclone.conf').unlink(missing_ok=True)
 log('VM rclone config deleted')

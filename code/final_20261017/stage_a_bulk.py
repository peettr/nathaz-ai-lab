import subprocess,time,json,traceback
from pathlib import Path
R=Path('/content/final_cache');remote='gdrive:colab_cache/strata_v0.1.45_g4/data/mtp'
t=time.monotonic()
try:
 with (R/'mtp_bulk.log').open('w') as f:
  p=subprocess.Popen(['rclone','copy','/content/Strata-data/mtp',remote,'--ignore-existing','--transfers','2','--checkers','2','--drive-chunk-size','64M','--tpslimit','5','--retries','2','--low-level-retries','5','--stats','30s','--stats-one-line'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  print('bulk pid',p.pid,flush=True)
  while p.poll() is None:print('bulk heartbeat',round(time.monotonic()-t),flush=True);time.sleep(15)
  assert p.returncode==0,p.returncode
 copy_s=round(time.monotonic()-t,2)
 with (R/'mtp_check.log').open('w') as f:rc=subprocess.run(['rclone','check','/content/Strata-data/mtp',remote,'--checksum','--one-way'],stdout=f,stderr=subprocess.STDOUT).returncode
 assert rc==0,rc
 T=json.loads((R/'timings_a.json').read_text());T['mtp_bulk_copy']=copy_s;T['mtp_check']=round(time.monotonic()-t-copy_s,2)
 (R/'timings_a.json').write_text(json.dumps(T,indent=2))
 (R/'stage_a.done').write_text(json.dumps(T))
 print('BULK_SUCCESS',T,flush=True)
except BaseException:
 print('ERROR',traceback.format_exc(),flush=True);(R/'stage_a.fail').write_text('bulk failed')
finally:
 Path('/root/.config/rclone/rclone.conf').unlink(missing_ok=True)
 print('CONFIG_REMOVED',not Path('/root/.config/rclone/rclone.conf').exists(),flush=True)

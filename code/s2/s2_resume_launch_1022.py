"""Colab short exec: detached install and frozen range 120:240 (10-22 disk-leak fix)."""
import os, pathlib, subprocess, sys
root=pathlib.Path('/content/s2'); root.mkdir(exist_ok=True)
log=(root/'resume_120_240.log').open('a', buffering=1)
env=os.environ.copy(); env.update(S2_START='120', S2_END='240', S2_PRIOR='/content/s2/ckpt_20_130_1022_0330_rescue.jsonl', S2_MIN_FREE_GB='10')
script='''import pathlib, subprocess, sys, traceback, os
try:
 for cmd in ([sys.executable,'-m','pip','install','-q','earth2studio[stormcast]==0.19.0'],[sys.executable,'-m','pip','install','-q','natten==0.21.6+torch2110cu130','-f','https://whl.natten.org']):
  print('INSTALL',cmd,flush=True); subprocess.run(cmd,check=True,timeout=900)
 import earth2studio,torch,natten
 print('ENV_OK',earth2studio.__version__,torch.__version__,torch.cuda.get_device_name(),flush=True)
 subprocess.run([sys.executable,'/content/s2_worker_resume_1022.py'],check=True)
except BaseException:
 print(traceback.format_exc(),flush=True)
 pathlib.Path('/content/s2/resume_120_240.failed').write_text(traceback.format_exc())
 raise
'''
(root/'resume_inner_20_130.py').write_text(script)
p=subprocess.Popen([sys.executable,str(root/'resume_inner_20_130.py')],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('RESUME_PID',p.pid,flush=True)

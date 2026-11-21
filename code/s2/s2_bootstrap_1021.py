"""One-shot Colab VM bootstrap: pin dependencies, assert imports, then pilot."""
import os,pathlib,subprocess,sys,time,traceback
R=pathlib.Path('/content/s2');R.mkdir(exist_ok=True)
try:
 for cmd in [['uv','pip','install','--system','earth2studio[stormcast]==0.19.0'],['uv','pip','install','--system','natten==0.21.6+torch2110cu130','--find-links','https://whl.natten.org']]:
  print('INSTALL',cmd,flush=True);subprocess.run(cmd,check=True,timeout=900)
 import earth2studio,torch,natten
 print('ENV_OK',earth2studio.__version__,torch.__version__,torch.cuda.get_device_name(),flush=True)
 env=os.environ.copy();env['S2_GROUP_LIMIT']='20'
 rc=subprocess.run([sys.executable,'/content/s2_worker_1021.py'],env=env,check=True).returncode
 assert rc==0
 (R/'bootstrap_exit.json').write_text('{"exit_code":0}')
except Exception:
 print(traceback.format_exc(),flush=True)
 (R/'bootstrap_exit.json').write_text('{"exit_code":1}')
 sys.exit(1)

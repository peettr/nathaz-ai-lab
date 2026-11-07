"""Colab-only detached installer and first frozen-cohort group."""
import json, os, pathlib, subprocess, sys, time, traceback
root=pathlib.Path('/content/s2');root.mkdir(exist_ok=True)
try:
    for cmd in ([sys.executable,'-m','pip','install','-q','earth2studio[stormcast]==0.19.0'],[sys.executable,'-m','pip','install','-q','natten==0.21.6+torch2110cu130','-f','https://whl.natten.org']):
        print('INSTALL',cmd,flush=True); subprocess.run(cmd,check=True,timeout=900)
    import earth2studio,torch,natten
    print('ENV_OK',earth2studio.__version__,torch.__version__,torch.cuda.get_device_name(),flush=True)
    env=os.environ.copy();env['S2_GROUP_LIMIT']='1'
    subprocess.run([sys.executable,'/content/s2_worker_1021.py'],env=env,check=True)
    print('PILOT_DONE',flush=True)
except Exception:
    print(traceback.format_exc(),flush=True)
    (root/'pilot_failed.json').write_text(json.dumps({'time':time.time(),'trace':traceback.format_exc()}))
    sys.exit(1)

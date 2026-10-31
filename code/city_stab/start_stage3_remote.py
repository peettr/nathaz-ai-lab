from pathlib import Path
import subprocess
Path('/content/.colab_owner').write_text('stage3_official_1015 researchos-uwind-luw')
p=subprocess.Popen(['python3','/content/run_stage3_remote.py'],stdin=subprocess.DEVNULL,stdout=open('/content/luw_stage3_driver.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('STAGE3_PID',p.pid,flush=True)

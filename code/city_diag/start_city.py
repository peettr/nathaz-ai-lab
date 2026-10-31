from pathlib import Path
import subprocess
Path('/content/.colab_owner').write_text('luw city_diag 2026-10-15 researchos-uwind-luw')
p=subprocess.Popen(['python3','/content/run_city.py'],stdout=open('/content/city_job.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('CITY_JOB_PID',p.pid,flush=True)

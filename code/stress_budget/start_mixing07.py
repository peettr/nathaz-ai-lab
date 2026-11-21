import subprocess
open('/content/.colab_owner','w').write('stress_budget tune delegation 10-15 18:40 researchos-uwind-luw')
p=subprocess.Popen(['python3','/content/run_mixing07.py'],stdout=open('/content/mixing07.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('TUNE_LAUNCHED',p.pid)

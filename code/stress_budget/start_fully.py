import subprocess
open('/content/.colab_owner','w').write('stress_budget full-y delegation 10-15 18:53 researchos-uwind-luw')
p=subprocess.Popen(['python3','/content/run_fully.py'],stdout=open('/content/fully.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('FULLY_LAUNCHED',p.pid)

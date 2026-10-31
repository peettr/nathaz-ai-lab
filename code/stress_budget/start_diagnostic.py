import subprocess
open('/content/.colab_owner','w').write('stress_budget delegation 10-15 18:17 researchos-uwind-luw')
p=subprocess.Popen(['python3','/content/run_diagnostic.py'],stdout=open('/content/stress.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',p.pid)

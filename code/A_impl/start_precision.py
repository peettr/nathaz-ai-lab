import subprocess,sys
p=subprocess.Popen(['python3','/content/run_precision_colab.py'],stdout=open('/content/precision.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('LAUNCHED',p.pid)

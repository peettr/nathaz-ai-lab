import subprocess,pathlib
p=subprocess.Popen(['python3','/content/run_gate0_colab_u012.py'],cwd='/content',stdin=subprocess.DEVNULL,stdout=open('/content/gate0_driver_u012.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
print('GATE0_U012_PID',p.pid)

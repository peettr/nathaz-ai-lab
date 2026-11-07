import subprocess,pathlib
r=pathlib.Path('/content')
p=subprocess.Popen(['python3','/content/run_gate0_colab_v2.py'],cwd=r,stdin=subprocess.DEVNULL,stdout=(r/'gate0_driver_v2.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
print('GATE0_PID',p.pid)

import subprocess,pathlib
p=pathlib.Path('/content/a3_b2_1014')
(p/'gate_fix3_started').open('x').write('started')
log=(p/'gate_fix3.log').open('w')
x=subprocess.Popen(['python3',str(p/'colab_gate_rate_B2_fix3.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('GATE_FIX3_PID',x.pid,flush=True)

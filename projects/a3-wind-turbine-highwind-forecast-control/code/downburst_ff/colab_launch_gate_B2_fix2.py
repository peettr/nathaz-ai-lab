import subprocess,pathlib
p=pathlib.Path('/content/a3_b2_1014')
(p/'gate_fix2_started').open('x').write('started')
log=(p/'gate_fix2.log').open('w')
x=subprocess.Popen(['python3',str(p/'colab_gate_rate_B2_fix2.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('GATE_FIX2_PID',x.pid,flush=True)

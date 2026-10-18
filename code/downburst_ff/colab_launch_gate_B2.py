import subprocess,pathlib
p=pathlib.Path('/content/a3_b2_1014')
(p/'gate_started').open('x').write('started')
log=(p/'gate.log').open('w')
x=subprocess.Popen(['python3',str(p/'colab_gate_rate_B2.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('GATE_PID',x.pid,flush=True)

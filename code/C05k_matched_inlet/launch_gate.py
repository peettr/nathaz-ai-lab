import subprocess, pathlib, time
p=pathlib.Path('/content/c05k_gate_01'); assert not p.exists()
owner=pathlib.Path('/content/.colab_owner');owner.write_text('luw-c05k-gate-1017 researchos-uwind-luw\n')
f=open('/content/c05k_launcher.log','w')
a=subprocess.Popen(['python3','/content/remote_gate.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('GATE_PID',a.pid,flush=True)

import subprocess,os
p='/content/l264diag04/venv/bin/python'
q=subprocess.run([p,'/content/colab04_diag_interp.py'],capture_output=True,text=True,timeout=120,env={**os.environ,'MPLBACKEND':'Agg'})
print(q.stdout[-3500:]);print(q.stderr[-1200:]);print('EXIT',q.returncode)

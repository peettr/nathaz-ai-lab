import subprocess
p='/content/l264diag04/venv/bin/python'
q=subprocess.run([p,'/content/colab04_diag_truth.py'],capture_output=True,text=True,timeout=120)
print(q.stdout[-3500:]);print(q.stderr[-1500:]);print('EXIT',q.returncode)

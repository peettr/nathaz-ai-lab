import importlib.util, subprocess
print('eccodes',importlib.util.find_spec('eccodes'))
r=subprocess.run(['python','-c','import eccodes; print(eccodes.__version__)'],capture_output=True,text=True,timeout=10)
print('subprocess',r.returncode,r.stdout,r.stderr[-500:])

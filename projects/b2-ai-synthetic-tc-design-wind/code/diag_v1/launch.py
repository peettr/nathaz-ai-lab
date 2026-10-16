import os,subprocess
marker='/content/diag_run.started'
fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
os.close(fd)
script='python /content/run_diag_colab.py > /content/diag_run.log 2>&1; code=$?; printf "%s\\n" "$code" > /content/diag_run.exit; if [ "$code" -eq 0 ]; then touch /content/diag_run.done; fi'
p=subprocess.Popen(['bash','-lc',script],start_new_session=True)
print('LAUNCHED',p.pid,flush=True)

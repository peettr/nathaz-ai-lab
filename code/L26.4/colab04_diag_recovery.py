import pathlib,subprocess,os,time,traceback
p=pathlib.Path('/content/l264diag04'); py=p/'venv/bin/python'; env={**os.environ,'MPLBACKEND':'Agg'}
try:
 for net in ('air','surface'):
  for variant in ('original','shift'):
   label=f'forecast_{net}_{variant}_retry';cmd=[str(py),'/content/colab04_diag_forecast.py','--net',net,'--region','shift','--variant',variant,'--days','1']
   with (p/(label+'.log')).open('x') as f:q=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
   if q.returncode:raise RuntimeError(f'{label} rc={q.returncode}')
   print('DONE',label,flush=True)
 with (p/'comparison_retry.log').open('x') as f:q=subprocess.run([str(py),'/content/colab04_diag_compare.py'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
 if q.returncode:raise RuntimeError(f'comparison rc={q.returncode}')
 (p/'diag_recovery.done').write_text('ok\n');print('DIAG_COMPLETE',flush=True)
except BaseException:
 (p/'diag_recovery.failed').write_text(traceback.format_exc());traceback.print_exc();raise

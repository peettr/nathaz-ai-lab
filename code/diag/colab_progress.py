from pathlib import Path
p=Path('/content/diag_run.log')
print('log:',p.read_text()[-4500:] if p.exists() else 'absent')
for n in ('diag_run.done','diag_run.failed'):
 q=Path('/content')/n;print(n,q.exists(),q.read_text()[-1500:] if q.exists() else '')

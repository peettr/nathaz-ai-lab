import pathlib,os
p=pathlib.Path('/content/t7_out');p.mkdir(exist_ok=True)
q=p/'run.failed'
if not q.exists():q.open('x').write('pre-launch budget/memory gate; no solver started\n')
print('PRELAUNCH_FAILED',flush=True)

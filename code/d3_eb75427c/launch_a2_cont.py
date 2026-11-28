import os, pathlib, subprocess
r=pathlib.Path('/content/l2631/d3'); (r/'a2_cont.started').open('x').write('started')
log=(r/'a2_cont.log').open('x')
code='''import pathlib,subprocess,time,sys
r=pathlib.Path('/content/l2631/d3')
for i in range(240):
 if (r/'embeddings.done').exists() and pathlib.Path('/content/l2631/weatherbench/stage.done').exists():break
 if i%2==0:print('WAIT_STAGE',i,flush=True)
 time.sleep(30)
else:sys.exit('stage not ready in 2h')
print('INPUTS_READY',flush=True)
cmd=['python','-u',str(r/'train_d3.py'),'--embed',str(r/'embeddings'),'--mismatch',str(r/'mismatch_v2.json'),'--out',str(r/'results'),'--drive','gdrive:colab_cache/L26.31/d3_eb75427c','--arms','A2','--seeds','11','23','37']
p=subprocess.run(cmd,stdout=sys.stdout,stderr=subprocess.STDOUT)
print('A2_EXIT',p.returncode,flush=True)
if p.returncode==0 and all((r/'results'/f'a2_seed{s}_metrics.json').exists() for s in (11,23,37)):
 (r/'a2_cont.done').write_text('done')
else:(r/'a2_cont.failed').write_text(str(p.returncode))
'''
subprocess.Popen(['python','-u','-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('A2_CONTROLLER_STARTED')

import pathlib, subprocess
r = pathlib.Path('/content/l2631/d3')
assert (r/'a2_cont.done').exists() and (r/'embeddings.done').exists()
assert pathlib.Path('/content/l2631/weatherbench/stage.done').exists()
for seed in (11, 23, 37):
    assert (r/'results'/f'a2_seed{seed}_metrics.json').exists()
with (r/'a3_cont.started').open('x') as f:
    f.write('started')
log = (r/'a3_cont.log').open('x')
code = '''import pathlib,subprocess,sys
r=pathlib.Path('/content/l2631/d3')
cmd=['python','-u',str(r/'train_d3.py'),'--embed',str(r/'embeddings'),'--mismatch',str(r/'mismatch_v2.json'),'--out',str(r/'results'),'--drive','gdrive:colab_cache/L26.31/d3_eb75427c','--arms','A3','--seeds','11','23','37']
p=subprocess.run(cmd,stdout=sys.stdout,stderr=subprocess.STDOUT)
print('A3_EXIT',p.returncode,flush=True)
if p.returncode==0 and all((r/'results'/f'a3_seed{s}_metrics.json').exists() for s in (11,23,37)):
 (r/'a3_cont.done').write_text('done')
else:(r/'a3_cont.failed').write_text(str(p.returncode))
'''
subprocess.Popen(['python','-u','-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('A3_CONTROLLER_STARTED')

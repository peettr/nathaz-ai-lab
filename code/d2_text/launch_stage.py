import pathlib,subprocess,sys
p=pathlib.Path('/content/l2631'); p.mkdir(exist_ok=True)
log=p/'d2_stage.log'
with log.open('x') as out:
 subprocess.Popen([sys.executable,'-u',str(p/'stage_weatherbench.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
print('D2_STAGE_STARTED')

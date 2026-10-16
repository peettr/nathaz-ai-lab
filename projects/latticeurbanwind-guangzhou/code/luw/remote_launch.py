import os,subprocess,pathlib
r=pathlib.Path('/content/luw-aij'); repo=r/'repo'; env=os.environ.copy(); env['LUW_HOME']=str(repo); env['PATH']=str(repo/'bin')+':'+env['PATH']; env['PYTHON']=str(repo/'.venv/bin/python')
for label,cmd,cwd in [
 ('install',['bash',str(repo/'installer/2_setup_python.sh')],repo),
 ('compile',['make','Linux','-j2'],repo/'core/cfd_core/FluidX3D')]:
 f=(r/f'{label}.log').open('w'); p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print(label,'PID',p.pid,'command',cmd,flush=True)
# These two stages run concurrently; later check return codes via processes or log and ELF presence.

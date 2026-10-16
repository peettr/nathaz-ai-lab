import os,subprocess,time,pathlib
root=pathlib.Path('/content/luw-aij'); root.mkdir(exist_ok=True)
def run(label,cmd):
 t=time.time(); p=subprocess.run(cmd,shell=True,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
 (root/f'{label}.log').write_text(f'$ {cmd}\n'+p.stdout+f'\nEXIT={p.returncode} WALL={time.time()-t:.2f}s\n')
 print(label,'exit',p.returncode,'wall',round(time.time()-t,1),p.stdout[-2500:],flush=True)
 return p.returncode
run('clone','git clone https://github.com/hweifluids/LatticeUrbanWind.git repo')
run('provenance','git -C repo rev-parse HEAD; git -C repo tag -l; git -C repo log -1 --format="%H %ai %s"; nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader; clinfo -l')
run('config',"python -c \"from pathlib import Path; p=Path('repo/examples/example_ProfileResearch_noDEM/conf.luwpf'); s=p.read_text().replace('n_gpu = [2, 1, 1]', 'n_gpu = [1, 1, 1]').replace('angle = [0, 90, 180, 270]', 'angle = [0]'); p.write_text(s)\"; git -C repo diff -- examples/example_ProfileResearch_noDEM/conf.luwpf")
# Spawn setup without holding a silent Colab kernel. The installer modifies only this fresh clone's venv.
cmd='export LUW_HOME=/content/luw-aij/repo; /usr/bin/time -v bash "$LUW_HOME/installer/2_setup_python.sh"; rc=$?; echo INSTALL_EXIT=$rc; exit $rc'
with (root/'install.log').open('w') as f:
 p=subprocess.Popen(['bash','-lc',cmd],cwd=root,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('INSTALL_PID',p.pid,flush=True)

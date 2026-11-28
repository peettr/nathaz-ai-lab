import pathlib,subprocess,time
r=pathlib.Path('/content/t3_run2_out');launch=pathlib.Path('/content/t3_run2_stage/launch.pid')
print('RUN2_PROBE',time.time(),'launch',launch.read_text().strip() if launch.exists() else 'absent','done',(r/'run.done').exists(),'failed',(r/'run.failed').exists())
if r.exists():
 for p in sorted(r.glob('*.zip')):print('ZIP',p.name,p.stat().st_size)
 for p in sorted(r.glob('*_exit.json')):print('EXIT',p.name,p.read_text()[-300:])
 for p in sorted(r.glob('*_solver.log')):print('SOLVER_LOG',p.name,p.stat().st_size,p.read_text(errors='replace')[-700:])
 log=r/'run.log'
 if log.exists():print('LOG',log.read_text(errors='replace')[-1400:])
print('PROCESS',subprocess.run(['pgrep','-af','remote_worker.py'],capture_output=True,text=True).stdout[-500:])

import pathlib,json,subprocess,time
r=pathlib.Path('/content/t3_out'); launch=pathlib.Path('/content/t3_stage/launch.pid')
print('PROBE',time.time(),'launch',launch.read_text().strip() if launch.exists() else 'absent','done',(r/'run.done').exists(),'failed',(r/'run.failed').exists())
if r.exists():
 for p in sorted(r.glob('*.zip')):print('ZIP',p.name,p.stat().st_size)
 log=r/'run.log'
 if log.exists():print('LOG',log.read_text(errors='replace')[-1400:])
print('PROCESS',subprocess.run(['pgrep','-af','remote_worker.py'],capture_output=True,text=True).stdout[-500:])

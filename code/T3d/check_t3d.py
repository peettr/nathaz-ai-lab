import pathlib,subprocess,time
r=pathlib.Path('/content/t3_t3d_out');root=pathlib.Path('/content/t3_t3d_stage')
print('T3D_PROBE',time.time(),'launch', (root/'launch.pid').read_text().strip() if (root/'launch.pid').exists() else 'absent','done',(r/'run.done').exists(),'failed',(r/'run.failed').exists())
if r.exists():
 for p in sorted(r.glob('*_thin.npz')):print('THIN',p.name,p.stat().st_size,(r/(p.name.replace('.npz','.sha256'))).read_text().strip())
 for p in sorted(r.glob('*_verified.ack')):print('ACKED',p.name.replace('_verified.ack',''),p.read_text().strip())
 for p in sorted(r.glob('*_exit.json')):print('EXIT',p.name,p.read_text()[-300:])
 print('FAIL',(r/'run.failed').read_text()[-800:] if (r/'run.failed').exists() else 'none')
log=root/'t3d.log'
if log.exists():print('LOG',log.read_text(errors='replace')[-1600:])
print('PROCESS',subprocess.run(['pgrep','-af','remote_worker_t3d.py'],capture_output=True,text=True).stdout[-400:])

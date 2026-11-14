import pathlib,subprocess
r=pathlib.Path('/content/L26_18_v3')
print('FILES',[(p.name,p.stat().st_size) for p in r.glob('*') if p.suffix in ('.json','.log') or p.name in ('exitcode','done')])
print('LOG', (r/'worker.log').read_text()[-2400:] if (r/'worker.log').exists() else 'absent')
print('EXIT',(r/'exitcode').read_text() if (r/'exitcode').exists() else 'running')
print('PROCESS',subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout.split('run_bc_v3.py')[0][-200:])

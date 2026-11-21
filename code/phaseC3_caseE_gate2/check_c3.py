import os,signal,subprocess,pathlib
for pid in (5756,5814):
 try:os.kill(pid,signal.SIGTERM);print('stopped duplicate',pid)
 except ProcessLookupError:print('already gone',pid)
r=pathlib.Path('/content/luw_c3_gate2_1016')
print('progress', (r/'progress.log').read_text()[-2000:] if (r/'progress.log').exists() else 'none')
print('driver',pathlib.Path('/content/luw_c3_driver.log').read_text()[-1000:])
print('build',[(p.name,p.read_text()[-1200:]) for p in r.glob('H*/build.log')])
print('keepalive',subprocess.run(['pgrep','-af','run_c3_remote'],capture_output=True,text=True).stdout)

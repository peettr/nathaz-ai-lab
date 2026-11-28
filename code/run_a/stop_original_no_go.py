import os,signal
pid=4908
cmd=open(f'/proc/{pid}/cmdline','rb').read().replace(b'\0',b' ').decode()
print('candidate',pid,cmd)
assert 'chain_a_v2.py' in cmd and '--lead-frozen' in cmd and '/content/a_original_rows.csv' in cmd
os.kill(pid,signal.SIGTERM)
print('SIGTERM to owned frozen chain; deterministic node threshold preflight proved 15x3 impossible')

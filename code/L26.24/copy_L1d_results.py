"""Copy three small completed L1d results through an existing CRC master; never overwrite."""
import hashlib
import json
import subprocess
from pathlib import Path

base = Path(__file__).resolve().parent
socket = './.ssh/sockets/[邮箱]'
root = '/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d/cpu/out'
files = {'l1_timing.csv': 'l1_timing_1759817.csv',
         'l1_summary.json': 'l1_summary_1759817.json',
         'l1_ic_crosscheck.json': 'l1_ic_crosscheck_1759817.json'}
for source, dest in files.items():
    path = base / dest
    if path.exists():
        raise RuntimeError(f'existing result: {path}')
    cmd = ['/usr/bin/timeout', '-k', '5s', '60s', 'ssh',
           '-o', f'ControlPath={socket}', '-o', 'ControlMaster=no',
           '-o', 'BatchMode=yes', '-o', 'ProxyCommand=false',
           '-o', 'ConnectTimeout=20', '[邮箱]',
           f'cd {root} && sha256sum {source} && cat {source}']
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=70)
    if proc.returncode:
        raise RuntimeError(f'connection/read failed {source}: {proc.stderr.decode(errors="replace")}')
    header, data = proc.stdout.split(b'\n', 1)
    remote_hash, remote_name = header.decode().split(maxsplit=1)
    assert remote_name == source
    local_hash = hashlib.sha256(data).hexdigest()
    assert local_hash == remote_hash, (source, remote_hash, local_hash)
    with path.open('xb') as out:
        out.write(data)
    print(json.dumps({'source': source, 'local': str(path), 'bytes': len(data), 'sha256': local_hash}))

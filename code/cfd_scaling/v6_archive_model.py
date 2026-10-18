"""Archive one completed v6 Colab model through the existing CRC socket.

Never use a FIFO or a pipe as ssh/scp stdin. Local staging is a regular
sub-200 MB temporary file; delete it only after independently matching hashes.
Usage: python v6_archive_model.py sanity|group
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SESSION = 'ideas-urbantales-v6-1014'
HOST = '[邮箱]'
SOCKET = os.path.expanduser('~/.ssh/sockets/[邮箱]')
DEST = '/groups/kareem/[用户]/lab_urbantales_v6'
STAGE = Path('./22_Lab/06_Logs/cfd_scaling')
OPTS = ['-o', 'ControlPath=' + SOCKET, '-o', 'ControlMaster=no', '-o', 'BatchMode=yes', '-o', 'ProxyCommand=false']

def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main(segment):
    if segment not in ('sanity', 'group'):
        raise ValueError('segment must be sanity or group')
    remote_source = f'/content/v6_work/{segment}/model_selected_val_r2.pt'
    remote_name = f'v6_{segment}_model_selected_val_r2.pt'
    remote_dest = f'{DEST}/{remote_name}'
    # Check the existing master WITHOUT allowing a new connection.
    run(['ssh', '-O', 'check', '-o', 'ControlPath=' + SOCKET, 'x'], timeout=15)
    # All no-input ssh commands explicitly use -n. Never replace with a pipe.
    existence = run(['ssh', '-n', *OPTS, HOST,
                     f'test -d {DEST} && test ! -e {remote_dest}'], timeout=30)
    assert existence.returncode == 0
    stage = STAGE / f'.v6_{segment}_archive_{os.getpid()}_{int(time.time())}.pt'
    try:
        run(['colab', '--auth', 'oauth2', 'download', '-s', SESSION,
             remote_source, str(stage)], timeout=300)
        size = stage.stat().st_size
        if not (0 < size < 200_000_000):
            raise RuntimeError(f'Not a permitted small staging file: {size} bytes')
        local_sha = sha(stage)
        # scp reads a REGULAR FILE. It never receives a FIFO or streamed stdin.
        run(['scp', *OPTS, str(stage), f'{HOST}:{remote_dest}'], timeout=300,
            stdin=subprocess.DEVNULL)
        remote = run(['ssh', '-n', *OPTS, HOST,
                      f'sha256sum {remote_dest} && stat -c %s {remote_dest}'],
                     timeout=45, capture_output=True).stdout.strip().splitlines()
        remote_sha = remote[0].split()[0]
        remote_size = int(remote[1])
        if (local_sha, size) != (remote_sha, remote_size):
            raise RuntimeError(f'Mismatch: local {local_sha}/{size}, remote {remote_sha}/{remote_size}; staging retained')
        print(json.dumps({'segment': segment, 'crc_path': remote_dest,
                          'sha256': local_sha, 'bytes': size}, indent=2), flush=True)
        stage.unlink()  # explicit approval: remove this new temporary staging file only after verification
    except Exception:
        print(f'Archive incomplete; inspect local staging file if present: {stage}', file=sys.stderr)
        raise

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python v6_archive_model.py sanity|group')
    main(sys.argv[1])

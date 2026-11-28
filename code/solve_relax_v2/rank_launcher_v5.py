#!/usr/bin/env python3
"""Rank 0 full stdout; each other rank retains only its last 200 lines."""
import collections
import os
import subprocess
import sys
rank = int(os.environ['OMPI_COMM_WORLD_RANK'])
if rank == 0:
    os.execv(sys.executable, [sys.executable, sys.argv[1]])
# Child stdout and stderr are drained continuously; no growing per-rank file.
cmd = [sys.executable, '-u', sys.argv[1]]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        bufsize=0)
last = collections.deque(maxlen=200)
for line in proc.stdout:
    last.append(line[-8192:])
code = proc.wait()
with open('rank_%02d.tail.log' % rank, 'wb') as f:
    f.writelines(last)
sys.exit(code)

#!/usr/bin/env python3
"""Sample all [用户] processes on the allocated node every ten seconds."""
import subprocess, sys, time
with open(sys.argv[1], 'a', buffering=1) as f:
    f.write('epoch,rss_kb_sum,process_count\n')
    while True:
        r = subprocess.run(['ps', '-u', '[用户]', '-o', 'rss='], capture_output=True, text=True)
        vals = [int(x) for x in r.stdout.split() if x.isdigit()] if r.returncode == 0 else []
        f.write(f'{time.time():.3f},{sum(vals)},{len(vals)}\n')
        time.sleep(10)

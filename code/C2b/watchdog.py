#!/usr/bin/env python3
"""Abort only this job's isolated solver group when a phase stalls >5x."""
import json, os, signal, sys, time
pid=int(sys.argv[1]); case=sys.argv[2]; evidence=sys.argv[3]
start=time.monotonic(); prev_phase='baseline'; prev_count=0; last=start
# D0/G1 coarse measured baseline 157.6s; adjoint ~645s; each FD rerun
# ~158s. Multiply each by five, round UP.
limits={'baseline':800,'ADJOINT_START':3300,'ADJOINT_END':800}
while True:
 time.sleep(15)
 try:os.kill(pid,0)
 except ProcessLookupError:break
 try:
  rows=[json.loads(x) for x in open(case+'/g1_progress.jsonl') if x.strip()]
  phase=rows[-1]['phase'] if rows else 'baseline'
  if len(rows)!=prev_count:
   prev_phase=phase;prev_count=len(rows);last=time.monotonic()
 except (FileNotFoundError,ValueError,KeyError):phase=prev_phase
 limit=limits.get(phase,800)
 if time.monotonic()-last>limit:
  with open(evidence,'a') as f:
   f.write(f'{time.time()} watchdog phase={phase} stagnant_seconds={time.monotonic()-last:.1f} threshold={limit} pid={pid}\n');f.flush();os.fsync(f.fileno())
  try:os.killpg(pid,signal.SIGTERM)
  except ProcessLookupError:pass
  time.sleep(10)
  try:os.killpg(pid,signal.SIGKILL)
  except ProcessLookupError:pass
  break

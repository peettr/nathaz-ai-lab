#!/usr/bin/env python3
"""Sample sum of all live MPI-rank RSS under this UGE job every 10 s."""
import os, sys, time
out=sys.argv[1]; job=os.getenv('JOB_ID','')
with open(out,'a',buffering=1) as f:
 f.write('epoch,rss_kb_sum,ranks,job_id\n')
 while True:
  total=0;count=0
  for entry in os.scandir('/proc'):
   if not entry.name.isdigit():continue
   try:
    env=open(entry.path+'/environ','rb').read()
    if b'OMPI_COMM_WORLD_RANK=' not in env or (job and ('JOB_ID='+job).encode() not in env):continue
    for line in open(entry.path+'/status'):
     if line.startswith('VmRSS:'):
      total+=int(line.split()[1]);count+=1;break
   except (OSError,ValueError):continue
  f.write(f'{time.time():.3f},{total},{count},{job}\n')
  time.sleep(10)

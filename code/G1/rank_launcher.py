#!/usr/bin/env python3
"""D0h rank-output limiter adapted to G1 driver name."""
import os,sys
rank=int(os.environ['OMPI_COMM_WORLD_RANK'])
if rank:
    fd=os.open(os.devnull,os.O_WRONLY)
    os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
os.execv(sys.executable,[sys.executable,sys.argv[1]])

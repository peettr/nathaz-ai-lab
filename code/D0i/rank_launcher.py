#!/usr/bin/env python3
"""Keep rank zero output; discard all other ranks before expensive imports."""
import os
import sys

rank = int(os.environ["OMPI_COMM_WORLD_RANK"])
if rank != 0:
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    os.dup2(null, 2)
    os.close(null)
os.execv(sys.executable, [sys.executable, "adjoint_pilot.py"])

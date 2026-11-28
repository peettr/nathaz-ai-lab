from mpi4py import MPI
from collections import Counter
from pathlib import Path
import json, os, socket, sys
comm=MPI.COMM_WORLD
rank=comm.rank
host=socket.gethostname()
marker=Path(sys.argv[1]).read_text().strip()
info=comm.allgather((rank,host,marker))
# Actual inter-node MPI communication, not merely independent hostname output.
counts=Counter(h for _,h,_ in info)
assert len(counts)==2 and sorted(counts.values())==[48,48], counts
assert all(m==marker and marker for _,_,m in info)
local=sorted(r for r,h,_ in info if h==host)
remote=sorted(r for r,h,_ in info if h!=host)
peer=remote[local.index(rank)]
sent=comm.sendrecv((rank,host,marker),dest=peer,source=peer)
assert sent[1]!=host and sent[2]==marker
comm.Barrier()
if rank==0:
    print(json.dumps({'ranks':comm.size,'hosts':dict(counts),'marker':marker,'cross_node_sendrecv':True},sort_keys=True),flush=True)

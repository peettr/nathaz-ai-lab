from mpi4py import MPI
import json, socket, sys
c=MPI.COMM_WORLD
rank=c.rank
host=socket.gethostname()
marker=open(sys.argv[1]).read().strip()
hosts=c.allgather(host)
markers=c.allgather(marker)
# Exchange payload between one rank from each distinct host.
unique=sorted(set(hosts))
assert len(unique)==3, hosts
leaders=[hosts.index(h) for h in unique]
if rank in leaders:
    j=leaders.index(rank)
    dest=leaders[(j+1)%3]
    source=leaders[(j-1)%3]
    got=c.sendrecv((host,marker),dest=dest,source=source)
    assert got==(unique[(j-1)%3],marker),got
c.Barrier()
if rank==0:
    counts={h:hosts.count(h) for h in unique}
    assert sorted(counts.values())==[48,48,48],counts
    assert len(set(markers))==1
    print('MPI_HELLO_OK',json.dumps({'hosts':counts,'marker':marker,'leaders':leaders}),flush=True)

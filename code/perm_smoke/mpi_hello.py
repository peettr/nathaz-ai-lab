from mpi4py import MPI
from socket import gethostname
from collections import Counter
c=MPI.COMM_WORLD
assert c.size==48,c.size
h=Counter(c.allgather(gethostname()))
assert len(h)==1,h
assert c.allreduce(c.rank)==48*47//2
if c.rank==0: print('MPI_HELLO_OK',dict(h),MPI.Get_library_version().strip(),flush=True)

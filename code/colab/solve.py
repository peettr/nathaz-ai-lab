import json,subprocess,time
import numpy as np
import cupy as cp
from scipy.sparse import csc_matrix
import nvmath.bindings.cudss as cudss
from nvmath.sparse.advanced import DirectSolver
A=csc_matrix([[4.,1.,0.],[1.,3.,1.],[0.,1.,2.]],dtype=np.float64).tocsr()
b=np.asarray([1.,2.,3.],dtype=np.float64)
t=time.perf_counter()
with DirectSolver(A,b) as s:
    s.plan();s.factorize();x=s.solve()
res=float(np.linalg.norm(A@x-b)/np.linalg.norm(b))
print(json.dumps(dict(gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip(),cudss_version=[cudss.get_property(0),cudss.get_property(1)],nvmath_version=__import__('nvmath').__version__,dtype=str(x.dtype),x=np.asarray(x).tolist(),relative_residual=res,elapsed_s=time.perf_counter()-t)),flush=True)
assert res<1e-10

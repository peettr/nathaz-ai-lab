import subprocess,sys,time,json
print('GPU',subprocess.run(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],capture_output=True,text=True).stdout,flush=True)
p=subprocess.run([sys.executable,'-m','pip','install','-q','nvidia-cudss-cu12','nvmath-python'],capture_output=True,text=True,timeout=180)
print('INSTALL_RC',p.returncode,p.stderr[-1500:],flush=True)
if p.returncode: raise SystemExit(p.returncode)
import nvmath
import nvmath.sparse.advanced as adv
print('NVMATH',nvmath.__version__,'ADV',dir(adv),flush=True)
import cupy as cp
from scipy.sparse import csc_matrix
A=csc_matrix([[4.,1.,0.],[1.,3.,1.],[0.,1.,2.]])
b=cp.asarray([1.,2.,3.],dtype=cp.float64)
print('START',flush=True)
with adv.DirectSolver(A,b) as solver:
    solver.plan()
    solver.factorize()
    x=solver.solve()
print('RESULT',cp.asnumpy(x).tolist(),'RESIDUAL',float(cp.linalg.norm(cp.asarray(A.toarray())@x-b)/cp.linalg.norm(b)),flush=True)

#!/usr/bin/env python3
"""L22.11 v2（选 2，由 3b driver_3a.py f67c6d87… 改两处：① L22_MODE=base 只跑基线、=endpoints 只跑四个端点；② 端点冷启动重置改为「本进程已跑过一次才重置」）。原注：L22.11 3a：J 对 v2/v3 方向的中心差分端点（不做伴随）。改自 L26.21 c2b_driver.py（sha256 4809f7e5…）。
- 方向向量在 DAFoam 全局序（各 processor 局部单元按 rank 拼接）下构造：每个 rank 读本次运行自己的
  processor<rank>/constant/polyMesh/cellProcAddressing，取串行 0/C 中心判盒，再按 rank 顺序拼接。
- 每次原问题（基线、v2±、v3±）都从同一冷启动初场开始 3000 步；结束后把该时间目录改名为 idx/1e4 保存，
  由作业脚本 reconstructPar + foamToVTK 取建筑表面 p，jcalc.py 离线算 J。"""
import json, math, os, re, sys, time, hashlib
from pathlib import Path
import numpy as np
from mpi4py import MPI
import openmdao.api as om
from mphys.core import Multipoint
from mphys.scenarios import ScenarioAerodynamic
from dafoam.mphys import DAFoamBuilder
comm=MPI.COMM_WORLD
def abort(kind,value,tb):
    sys.__excepthook__(kind,value,tb); comm.Abort(89)
sys.excepthook=abort
case=Path.cwd(); n=json.loads((case/'sample_cells.json').read_text())['mesh_cells']; grade=os.environ['L22_GRADE']; mode=os.environ['L22_MODE']; assert mode in ('base','endpoints')
assert grade in ('medium','fine','finer') and n>100000
u_ref=float(json.loads((case/'empty_reference.json').read_text())['U_at_H']); assert 0<u_ref<30
H=1e-3
opts={'solverName':'DASimpleFoam','printInterval':1,'primalMinResTol':1e-12,'primalMinResTolDiff':1e20,
 'primalBC':{'useWallFunction':True},
 'function':{'roofCp':{'type':'patchMean','source':'patchToFace','patches':['roof'],'varName':'p','varType':'scalar','index':0,'scale':2.0/u_ref**2}},
 'normalizeStates':{'U':10.,'p':u_ref*u_ref/2,'nut':0.1,'phi':1.,'nuTilda':0.1},
 'inputInfo':{'beta':{'type':'field','fieldName':'betaFINuTilda','fieldType':'scalar','distributed':False,'components':['solver','function']}}}
class Top(Multipoint):
 def setup(self):
    b=DAFoamBuilder(options=opts,mesh_options=None,scenario='aerodynamic');b.initialize(self.comm)
    self.add_subsystem('dvs',om.IndepVarComp(),promotes=['*'])
    self.mphys_add_scenario('scenario1',ScenarioAerodynamic(aero_builder=b))
 def configure(self):
    self.dvs.add_output('beta',val=np.ones(n),distributed=False)
    self.connect('beta','scenario1.beta');self.add_design_var('beta',lower=.2,upper=5.)
    self.add_objective('scenario1.aero_post.roofCp')
prob=om.Problem(model=Top());prob.setup(mode='rev')
name='scenario1.aero_post.roofCp'; beta=np.ones(n)
solver=prob.model.scenario1.coupling.solver; DAS=solver.DASolver
def status(phase,**d):
 if comm.rank==0:
    with (case/'l22_progress.jsonl').open('a') as f: f.write(json.dumps({'phase':phase,'at':time.time(),**d})+'\n');f.flush();os.fsync(f.fileno())
 comm.Barrier()
# ---- 方向向量（DAFoam 全局序） ----
def read_labels(p):
    t=p.read_text()
    if not re.search(r'\bformat\s+ascii\s*;',t[:4096]): raise ValueError(f'{p}: not ascii')
    L=list(re.finditer(r'(?m)^\s*(\d+)\s*\n\s*\(',t)); assert len(L)==1,p
    m=L[0]; c=int(m.group(1)); tail=t[m.end():]; e=re.search(r'(?m)^\s*\)\s*;?\s*$',tail)
    a=np.asarray(tail[:e.start()].split(),dtype=np.int64); assert len(a)==c; return a
from physical_directions import read_centres
C=read_centres(case/'serial_C',n)
cpa=read_labels(case/f'processor{comm.rank}/constant/polyMesh/cellProcAddressing')
x,y,z=C[cpa].T
loc={'v2':((x>=-16)&(x<=16)&(y>=-16)&(y<=16)&(z>=0)&(z<=16)).astype(float),
     'v3':((x>=8)&(x<=48)&(y>=-12)&(y<=12)&(z>=0)&(z<=12)).astype(float)}
allcpa=np.concatenate(comm.allgather(cpa)); assert len(allcpa)==n and np.array_equal(np.sort(allcpa),np.arange(n))
vec={k:np.concatenate(comm.allgather(v)) for k,v in loc.items()}
for k,v in vec.items(): assert len(v)==n and v.sum()>0
if comm.rank==0:
 (case/'l22_directions.json').write_text(json.dumps({'n':n,'grade':grade,'ranks':comm.size,'perm_sha256':hashlib.sha256(allcpa.tobytes()).hexdigest(),
  'directions':{k:{'count':int(v.sum()),'sha256':hashlib.sha256(v.tobytes()).hexdigest()} for k,v in vec.items()}},indent=2)+'\n')
if comm.rank==0: np.save(case/'l22_perm.npy',allcpa)
status('DIRECTIONS_BUILT')
# ---- 原问题 ----
def logtext(): return (case/'g1_rank0.log').read_text(errors='replace')
def residuals(txt):
 out={}
 for k,v in re.findall(r'Solving for\s+([A-Za-z][A-Za-z0-9]*),\s+Initial residual\s*=\s*([0-9.eE+-]+)',txt):
    v=float(v)
    if math.isfinite(v): out.setdefault(k,[]).append(v)
 assert len(out['p'])==3*len(out['Ux']); out['p']=out['p'][0::3]; return out
def cp_trace(txt): return [float(v) for v in re.findall(r'^\s*roofCp:\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)',txt,re.M)]
FIELDS=['Ux','Uy','Uz','p','nuTilda']
initial_state=DAS.getStates().copy()
manifest=[]
ran=[False]
def run(idx,label,target,tol):
 if ran[0]:  # 基线用 DAFoam 刚初始化的初场；端点回到同一初场冷启动（r2 修正：首次 run_model 前 _outputs 为 None）
  DAS.setStates(initial_state.copy()); solver._outputs[solver.stateName]=initial_state.copy()
 beta[:]=target
 if comm.rank==0: before=({f:len(v) for f,v in residuals(logtext()).items()} if (case/'g1_rank0.log').exists() and 'Solving for' in logtext() else {}); ncp=len(cp_trace(logtext())) if (case/'g1_rank0.log').exists() else 0
 prob.set_val('beta',beta); t=time.monotonic(); prob.run_model(); comm.Barrier()
 cp=float(np.asarray(prob.get_val(name)).ravel()[0])
 tname,ren=DAS.renameSolution(idx); comm.Barrier()
 if comm.rank==0:
  txt=logtext(); r=residuals(txt); fresh={f:r[f][before.get(f,0):] for f in FIELDS}; tr=cp_trace(txt)[ncp:]
  ratios={f:(v[-1]/v[0] if v and v[0] else None) for f,v in fresh.items()}
  dcp=abs(tr[-1]-tr[-500])/max(abs(tr[-500]),1e-6) if len(tr)>=500 else None
  ok=all(len(fresh[f])==3000 and ratios[f] is not None and ratios[f]<=tol for f in FIELDS) and dcp is not None and dcp<0.005 and ren
  row={'idx':idx,'label':label,'time':str(tname),'renamed':bool(ren),'roofCp':cp,'steps':len(fresh['Ux']),'residual_ratio':ratios,'roofCp_change_last500':dcp,'tol':tol,'valid':ok,'seconds':time.monotonic()-t}
  with (case/'l22_endpoints.jsonl').open('a') as f: f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
 else: row=None
 row=comm.bcast(row,root=0); status('PRIMAL',label=label,valid=row['valid'])
 ran[0]=True
 if not row['valid']: status('PRIMAL_GATE_FAILED',label=label); sys.exit(45)
 return row
if mode=='base':
 run(1,'BASE',np.ones(n),1e-4)
else:
 i=2
 for k in ('v2','v3'):
  for s in (1,-1):
   run(i,f'{k}_{"p" if s>0 else "m"}',1+s*H*vec[k],1e-6); i+=1
status('COMPLETE_'+mode)

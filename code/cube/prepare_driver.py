#!/usr/bin/env python3
"""Derive cube directional test from immutable C2a limiter-rand implementation."""
from pathlib import Path
base=Path(__file__).resolve().parent
src=base.parent/'C2a/limiter_rand/c2a_driver.py'
s=src.read_text()
a="assert n==168206 and ids==[51676,149479,154520,159137,159971]"
assert s.count(a)==1
s=s.replace(a,"assert n==227656, ('mesh_cells',n)")
a="ref=json.loads((case/'empty_reference.json').read_text()); u_ref=float(ref['U_at_H']); assert 0<u_ref<30"
assert s.count(a)==1
s=s.replace(a,"u_ref=1.0 # Paper PDF p.1 H=1 m, U=1 m/s; Cp reference is the fixed uniform inlet")
a="    assert len(r[f])==3000 for f in fields"
# guard above appears with all(...) below, do not mutate threshold.
s=s.replace("assert all(len(r[f])==3000 for f in fields)","assert all(len(r[f])==3000 for f in fields)")
s=s.replace("'prior_adjoint_dot':-2.78108326209e-4,'prior_difference':dot-(-2.78108326209e-4)","'objective':'roof-mean Cp','direction':'normal_seed2621'")
s=s.replace("for h in (1e-2,3e-3):\n ends=[]\n for sign in (1,-1):\n  target=1+sign*h*v\n  ends.append(cold_endpoint(f'DIR_normal_seed2621_{h}_{sign}',target))\n fd=(ends[0]['cp']-ends[1]['cp'])/(2*h)\n row={'kind':'direction','direction':'normal_seed2621','h':h,'adjoint_dot':dot,'fd':fd,\n      'relative_error':abs(dot-fd)/abs(fd) if fd else None,'endpoints':ends,'baseline_cp':base}","for label,direction,h in [(name,direction,step) for name,direction in [('ones',np.ones(n)),('normal_seed2621',v)] for step in (1e-3,3e-3,1e-2)]:\n direction_dot=comm.allreduce(float(np.dot(grad[chunk],direction[chunk])),op=MPI.SUM)\n ends=[]\n for sign in (1,-1):\n  target=1+sign*h*direction\n  ends.append(cold_endpoint(f'DIR_{label}_{h}_{sign}',target))\n fd=(ends[0]['cp']-ends[1]['cp'])/(2*h)\n row={'kind':'direction','direction':label,'h':h,'adjoint_dot':direction_dot,'fd':fd,\n      'relative_error':abs(direction_dot-fd)/abs(fd) if fd else None,'endpoints':ends,'baseline_cp':base}")
s=s.replace("status('DIRECTION_FD',direction='normal_seed2621',h=h)","status('DIRECTION_FD',direction=label,h=h)")
assert "for h in (1e-2,3e-3):" not in s and "assert n==227656" in s and "direction=label" in s
(base/'cube_driver.py').write_text(s)
print('generated',base/'cube_driver.py')

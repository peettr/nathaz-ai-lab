#!/usr/bin/env python3
"""Stage C2b from immutable, previously exercised C1/C2a inputs."""
from pathlib import Path
import hashlib, shutil

p = Path(__file__).resolve().parent
base = p.parent
c1 = base/'C1_SA'
c2 = base/'C2a/limiter_rand'
medium = base/'solve_v4'
p.mkdir(parents=True, exist_ok=True)
for src, name in [(c1/'patch_sa_case.py','patch_sa_case.py'),(c1/'build_sa_inlet.py','build_sa_inlet.py'),(c1/'fvSolution_C1','fvSolution_C1'),(c1/'snappyHexMeshDict_B2','snappyHexMeshDict_B2'),(c1/'rank_launcher_v5.py','rank_launcher_v5.py'),(c1/'launch_solve.sh','launch_solve.sh'),(c1/'watchdog.py','watchdog.py'),(c2/'harvest.py','harvest.py'),(c2/'rss_sampler.py','rss_sampler.py'),(c2/'remove_limiter.py','remove_limiter.py')]:
    dst=p/name
    assert not dst.exists(), dst
    shutil.copy2(src,dst)
for name in ('check_field_boundaries.py',):
    src=base/name; dst=p/name
    assert not dst.exists(),dst
    shutil.copy2(src,dst)
s=(c2/'c2a_driver.py').read_text()
s=s.replace('"""C2a diagnostic cells only; original five-cell gate remains unchanged."""','"""C2b SA medium directional derivatives (frozen Liang Hu-accepted gate)."""')
s=s.replace("n=sample['mesh_cells']; ids=sample['cell_ids']\nassert n==168206 and ids==[51676,149479,154520,159137,159971]", "n=sample['mesh_cells']\nassert n==506198, n")
s=s.replace("# The 3000-step baseline was prechecked against the C1 SA coarse log.","# Cold 3000-step baseline and endpoints, C1 SA medium mesh rebuilt from same inputs.")
s=s.replace("status('DIRECTIONS_START')\nfor h in (1e-2,3e-3):\n ends=[]", "status('DIRECTIONS_START')\nfrom collections import OrderedDict\nvectors=OrderedDict([('all_ones',np.ones(n)),('normal_seed2621',v)])\nsequence=[('all_ones',1e-3),('normal_seed2621',1e-3),('normal_seed2621',1e-2),('normal_seed2621',3e-3),('all_ones',1e-2)]\nfor direction,h in sequence:\n v=vectors[direction]\n chunk=np.array_split(np.arange(n),comm.size)[comm.rank]\n dot=comm.allreduce(float(np.dot(grad[chunk],v[chunk])),op=MPI.SUM)\n ends=[]")
s=s.replace("f'DIR_normal_seed2621_{h}_{sign}'", "f'DIR_{direction}_{h}_{sign}'")
s=s.replace("'direction':'normal_seed2621','h':h", "'direction':direction,'h':h")
s=s.replace("status('DIRECTION_FD',direction='normal_seed2621',h=h)", "status('DIRECTION_FD',direction=direction,h=h)")
s=s.replace("'prior_adjoint_dot':-2.78108326209e-4,'prior_difference':dot-(-2.78108326209e-4)", "'direction':'normal_seed2621'")
assert "assert n==506198" in s and "sequence=[('all_ones',1e-3)" in s and "p'][0::3]" in s
(p/'c2b_driver.py').write_text(s)
print('PREPARED',[(f.name,hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(p.iterdir()) if f.is_file()])

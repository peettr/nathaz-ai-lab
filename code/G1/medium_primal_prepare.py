#!/usr/bin/env python3
"""Create a new, immutable medium-primal diagnostic package from relax_v2."""
from pathlib import Path
import shutil, hashlib, difflib
base=Path(__file__).parent
src=base/'solve_relax_v2'
out=base/'medium_primal'
assert not out.exists(), 'Refuse to overwrite existing package'
out.mkdir()
for name in ('rank_launcher_v5.py','launch_solve.sh','harvest.py','watchdog.py','fvSolution','g1_driver.py'):
    shutil.copy2(src/name,out/name)
p=out/'g1_driver.py'
s=p.read_text()
needle="status('ADJOINT_START',{})"
assert s.count(needle)==1
s=s.replace(needle,"status('MEDIUM_PRIMAL_ONLY',{'primal_gate':True})\nsys.exit(0)\n"+needle)
p.write_text(s)
w=out/'watchdog.py'; s=w.read_text(); assert "'baseline':800" in s;s=s.replace("'baseline':800","'baseline':2400");w.write_text(s)
qsrc=(src/'g1_coarse_relax_v2.qsub').read_text()
q=qsrc.replace('L26_21_G1_coarse_relax_v2','L26_21_G1_medium_primal').replace('L26_21_DAFOAM_20261114_G1_coarse_relax_v2','L26_21_DAFOAM_20261114_G1_medium_primal').replace('L26_21_DAFOAM_20261114_G1_coarse_v4','L26_21_DAFOAM_20261114_G1_medium_v4').replace('G=coarse','G=medium')
assert q!=qsrc and 'G=coarse' not in q and 'G1_coarse_v4' not in q
# A full 48-slot PE occupies a whole 48-slot node; request explicit exclusive placement.
q=q.replace('#$ -pe mpi-48 48','#$ -pe mpi-48 48\n#$ -l exclusive=true')
# This diagnostic performs primal only; it does not need a reconstructed field.
q=q.split('# Optional final reconstructed state.')[0]+'stage COMPLETE PRIMAL_ONLY\n'
(out/'g1_medium_primal.qsub').write_text(q)
(out/'relax_v2_to_medium_primal.diff').write_text(''.join(difflib.unified_diff(qsrc.splitlines(True),q.splitlines(True),fromfile='coarse_relax_v2.qsub',tofile='g1_medium_primal.qsub')))
for f in out.iterdir():
    if f.is_file(): print(f.name,hashlib.sha256(f.read_bytes()).hexdigest())

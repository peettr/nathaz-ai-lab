"""Stage three immutable, disjoint mesh-convergence job inputs."""
from pathlib import Path
import shutil,hashlib,re,json
base=Path(__file__).resolve().parent
source=base.parent/'C2b/tacc/production'
assert source.is_dir()
for grade,shape,slots,wall in [('coarse','80 48 38',48,'03:00:00'),('medium','130 70 50',48,'05:00:00'),('fine','150 80 58',24,'08:00:00')]:
    root=base/grade
    assert not root.exists(),root
    root.mkdir()
    for name in ('c2b_driver.py','physical_directions.py','patch_sa_case.py','build_sa_inlet.py','check_field_boundaries.py','remove_limiter.py','rank_launcher_v5.py','snappyHexMeshDict_B2','fvSolution_C1','meshconv_worker.sh','harvest_meshconv.py'):
        shutil.copy2(base/'package'/name,root/name)
    c=root/'case_inputs';shutil.copytree(source/'case_inputs',c)
    b=c/'system/blockMeshDict';s=b.read_text();s,count=re.subn(r'\(130 70 50\)',f'({shape})',s);assert count==1;b.write_text(s)
    for stale in c.rglob('processor*'):raise ValueError(stale)
    remote=f'/groups/kareem/[用户]/L26_21_DAFOAM_20261120_meshconv/{grade}'
    script=f'''#!/usr/bin/env bash
#$ -N L26_21_mc_{grade}
#$ -cwd
#$ -j y
#$ -q hpc@d24cepyc0*
#$ -pe mpi-48 {slots}
#$ -l m_mem_free=2G
#$ -l hostname=!d24cepyc154*&!d24cepyc161*&!d24cepyc162*
#$ -l h_rt={wall}
set -uo pipefail
R={remote}
I=/groups/kareem/[用户]/L26_21_DAFOAM_20261113/img/dafoam_v5.1.1.sif
GRADE={grade}
cd "$R" || exit 80
mkdir -p logs
trap 'rc=$?; printf "%s\\n" "$rc" > "$R/logs/meshconv.exitcode"; du -sB1 "$R" >> "$R/logs/du_final.txt"; sync "$R/logs/meshconv.exitcode"; exit "$rc"' EXIT
[ "${{NSLOTS:-0}}" -eq {slots} ] || exit 81
[ -r "$I" ] || exit 82
for f in c2b_driver.py physical_directions.py patch_sa_case.py build_sa_inlet.py check_field_boundaries.py remove_limiter.py rank_launcher_v5.py snappyHexMeshDict_B2 fvSolution_C1 meshconv_worker.sh harvest_meshconv.py case_inputs/0/U case_inputs/system/blockMeshDict case_inputs/empty_reference.json; do [ -f "$R/$f" ] || {{ echo "MISSING $f"; exit 82; }}; done
[ ! -e "$R/case_inputs/processor0" ] || exit 83
BASE=${{TMPDIR:-/tmp}}
[ -d "$BASE" ] && [ -w "$BASE" ] || exit 84
FREE=$(df -PB1 "$BASE" | awk 'NR==2{{print $4}}')
[ "${{FREE:-0}}" -ge 20000000000 ] || exit 84
W=$(mktemp -d "$BASE/L26_21_mc_{grade}_XXXXXXXX") || exit 85
mkdir -p "$W/cache" "$W/tmp" "$W/home" "$W/numba"
export APPTAINER_CACHEDIR="$W/cache" APPTAINER_TMPDIR="$W/tmp" TMPDIR="$W/tmp" HOME="$W/home" R W I GRADE MESHCONV_GRADE="$GRADE"
# All allocated runtime is bounded by the approved per-grade wall limit.
timeout --signal=TERM --kill-after=10s { {'coarse':10500,'medium':17700,'fine':28500}[grade]}s bash "$R/meshconv_worker.sh"
'''
    (root/'meshconv.qsub').write_text(script)
    manifest=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name!='inputs.sha256':
            manifest.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}')
    (root/'inputs.sha256').write_text('\n'.join(manifest)+'\n')
    print(grade,remote,len(manifest),hashlib.sha256((root/'meshconv.qsub').read_bytes()).hexdigest())

from pathlib import Path
import shutil, hashlib, re, subprocess
base=Path(__file__).parent
src=base/'perm_smoke'
out=base/'inner_mpi_smoke'
if out.exists():
    raise SystemExit(f'Already exists: {out}; inspect before retry')
out.mkdir()
for name in ('smoke_inputs','snappyHexMeshDict_B2','fvSolution_C1','mpi_hello.py','smoke_driver.py','patch_sa_case.py','build_sa_inlet.py','check_field_boundaries.py','remove_limiter.py','expected_libs.sha256'):
    p=src/name
    if p.is_dir(): shutil.copytree(p,out/name)
    else: shutil.copy2(p,out/name)
text=(src/'perm_smoke.sbatch').read_text()
text=text.replace('L26_21_C2b_TACC_perm_smoke','L26_21_C2b_TACC_inner_mpi_smoke').replace('#SBATCH -t 01:30:00','#SBATCH -t 00:30:00').replace('L26_21_C2b_TACC_20261117_perm_smoke','L26_21_C2b_TACC_20261117_inner_mpi_smoke')
a=text.index('ORIG=/scratch/')
b=text.index('run(){',a)
text=text[:a]+'''I=/scratch/04448/[用户]/L26_21_C2b_TACC_20261117_perm_smoke/image/dafoam_v5.1.1.perm.3732881.sif
[[ -f "$I" && -r "$I" ]]
LIB=./dafoam/packages/miniconda3/lib/python3.12/site-packages/dafoam/libs
stage IMAGE_LIB_HASH_START
"$AP" exec --cleanenv --containall --no-home --pwd / "$I" /usr/bin/sha256sum "$LIB/pyDASolvers.cpython-312-x86_64-linux-gnu.so" "$LIB/pyUnitTests.cpython-312-x86_64-linux-gnu.so" > logs/image_identity.txt 2> logs/image_identity.stderr
if ! cmp -s expected_libs.sha256 logs/image_identity.txt; then stage IMAGE_LIB_HASH_MISMATCH; exit 42; fi
stage IMAGE_LIB_HASH_MATCH
sha256sum "$I" > logs/repaired_sif.sha256
''' +text[b:]
text=text.replace('mpi(){ ibrun /bin/bash "$R/smoke_mpi_rank.sh" "$R" "$@"; }','mpi(){ run mpirun -np 48 "$@"; }').replace('MPI_HELLO_START_IBRUN','MPI_HELLO_START_CONTAINER_MPIRUN')
assert 'ibrun ' not in text and 'SMOKE_COMPLETE' in text
(out/'inner_mpi_smoke.sbatch').write_text(text)
files=sorted([p for p in out.rglob('*') if p.is_file() and p.name!='inputs.sha256'])
(out/'inputs.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in files if p.name!='inner_mpi_smoke.sbatch'))
print('root',out,'files',len(files),'sbatch_sha256',hashlib.sha256(text.encode()).hexdigest())

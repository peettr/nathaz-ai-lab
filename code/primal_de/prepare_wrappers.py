from pathlib import Path
p=Path(__file__).resolve().parent
src=p.parent/'primal_ab'
s=(src/'primal_worker.sh').read_text(); a=s.index('B="$W/cases/A"'); b=s.index(' cp "$R/primal_driver.py"',a)
s=s[:a]+'''for arm in D E F; do
 if [[ $arm = F ]] && (( $(date +%s) - JOB_STARTED > 1080 )); then stage F_SKIPPED_TIME; break; fi
 C="$W/cases/$arm"
 stage "$arm START"
 run blockMesh -case "$C" > "$C/blockMesh.log" 2>&1; rc=$?
 transfer "$C/blockMesh.log" "${arm}_blockMesh.log"; stage "$arm BLOCKMESH rc=$rc"
 ((rc==0)) || continue
 run checkMesh -case "$C" > "$C/checkMesh.log" 2>&1; rc=$?
 transfer "$C/checkMesh.log" "${arm}_checkMesh.log"; stage "$arm CHECKMESH rc=$rc"
 read -r cells < "$C/expected_cells"
 if ((rc!=0)) || ! grep -q 'Mesh OK' "$C/checkMesh.log" || ! grep -Eq "cells: +$cells([[:space:]]|$)" "$C/checkMesh.log"; then stage "$arm MESH_GATE_FAIL"; continue; fi
 if [[ $arm != E ]]; then
   run python "$R/set_inlet.py" "$C" > "$C/inlet_audit.log" 2>&1; rc=$?
   transfer "$C/inlet_audit.log" "${arm}_inlet_audit.log"; stage "$arm INLET_MAP rc=$rc"
   ((rc==0)) || continue
 fi
''' +s[b:]
s=s.replace(' stage "$arm START"\n setsid',' stage "$arm SOLVE_START"\n setsid').replace("'(^|[[:space:]])roof([[:space:]]|$)'","'patch (roof|front|back|cubeSideNeg|cubeSidePos) y\\+'").replace('"${arm}_roof_yplus.txt"','"${arm}_wall_yplus.txt"').replace('ABC_COMPLETE','DEF_COMPLETE')
s=s.replace('if ((u+b > 240000000));','if ((u+b > RETURN_CAP));')
(p/'primal_worker.sh').write_text(s)
s=(src/'primal_ab.qsub').read_text().replace('L26_21_cube_primal_ABC','L26_21_cube_primal_DEF').replace('cube_primal\n','cube_primal2\n').replace('hpc@d24cepyc0*','hpc').replace('"$R/launch_solve.sh";', '"$R/launch_solve.sh" "$R/set_inlet.py";')
s=s.replace('NATIVE_TMP=', '''JOB_STARTED=$(date +%s)
allocated=$(du -sB1 -c /groups/kareem/[用户]/L26_21* | awk '$2=="total"{print $1}')
[[ $allocated =~ ^[0-9]+$ ]] || exit 84
RETURN_CAP=$((14900000000 - allocated - 10000000)); ((RETURN_CAP > 0)) || exit 84
((RETURN_CAP <= 240000000)) || RETURN_CAP=240000000
export JOB_STARTED RETURN_CAP
NATIVE_TMP=''')
s=s.replace('timeout --signal=TERM --kill-after=10s 1680s','remain=$((1680 - $(date +%s) + JOB_STARTED)); ((remain>0)) || exit 84\ntimeout --signal=TERM --kill-after=10s "${remain}s"')
(p/'primal_de.qsub').write_text(s)

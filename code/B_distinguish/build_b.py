from pathlib import Path
import shutil, re, hashlib, json
base=Path(__file__).resolve().parent
src=base.parent/'solve_relax_v2'
root='/groups/kareem/[用户]/L26_21_DAFOAM_20261114_B_distinguish'
for name in ('rank_launcher_v5.py','launch_solve.sh','watchdog.py','harvest.py'):
 shutil.copy2(src/name,base/name)
fv=(src/'fvSolution').read_text().replace('nNonOrthogonalCorrectors 0','nNonOrthogonalCorrectors 2')
assert 'nNonOrthogonalCorrectors 2' in fv
(base/'fvSolution').write_text(fv)
driver=(src/'g1_driver.py').read_text()
# No adjoint in this experiment; preserve the identical primal and gate implementation.
driver=driver[:driver.index("status('ADJOINT_START',{})")]
(base/'b_driver.py').write_text(driver)
# Roof-only layers; original unlayered G1 case remains immutable.
snappy=(base.parent/'review_v5/cases/coarse/system/snappyHexMeshDict').read_text()
assert 'addLayers false;' in snappy and 'layers { }' in snappy
snappy=snappy.replace('addLayers false;', 'addLayers true;').replace('layers { }','layers { roof { nSurfaceLayers 3; } }')
# Absolute thickness is deliberately checked by measured roof y+, not assumed equivalent.
snappy=snappy.replace('relativeSizes true;', 'relativeSizes true;')
(base/'snappyHexMeshDict_B2').write_text(snappy)
q=(src/'g1_coarse_relax_v2.qsub').read_text().replace('L26_21_G1_coarse_relax_v2','L26_21_B_distinguish').replace('L26_21_DAFOAM_20261114_G1_coarse_relax_v2',root)
q=q.replace('h_rt=08:00:00','h_rt=01:00:00')
q=q.replace('cp "$R/g1_driver.py" "$C/g1_driver.py"','cp "$R/b_driver.py" "$C/g1_driver.py"')
# explicit complete file manifest; source remains G1 coarse_v4 and all execution is in node TMPDIR
q=q.replace('"$R/rank_launcher_v5.py"; do', '"$R/rank_launcher_v5.py" "$R/b_driver.py" "$R/fvSolution" "$R/launch_solve.sh" "$R/watchdog.py" "$R/harvest.py" "$R/snappyHexMeshDict_B2"; do')
# Keep B1 outputs in their own scratch case before B2; B2 is a fresh case copied from immutable source.
q=q[:q.index('if [ "$rec" -eq 0 ]; then')] + '''if [ "$rec" -eq 0 ]; then stage "$G/field" "node_local_only"; fi
# If B1 gate passes, B2 must NOT run. If not, create a clean mesh from the immutable unlayered case.
if [ -f "$C/g1_gate.json" ] && python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1]))["primal_gate"] else 1)' "$C/g1_gate.json"; then
 stage B1 GATE_PASS; stage COMPLETE B1_ONLY; exit 0
fi
stage B1 GATE_FAIL
B="$W/cases/B2"
cp -a "$SRC/cases/$G" "$B" || exit 82
cp "$R/b_driver.py" "$B/g1_driver.py"; cp "$R/fvSolution" "$B/system/fvSolution"
cp "$R/snappyHexMeshDict_B2" "$B/system/snappyHexMeshDict"
# Rebuild an independent roof-layered mesh; never reuse the already-snapped polyMesh.
[ -f "$B/system/blockMeshDict" ] && [ -f "$B/system/snappyHexMeshDict" ] || exit 82
stage B2/blockMesh START
run blockMesh -case "$B" > "$W/B2_blockMesh.log" 2>&1; brc=$?
stage B2/blockMesh "rc=$brc"; [ "$brc" -eq 0 ] || exit 31
stage B2/snappy START
run snappyHexMesh -case "$B" -overwrite > "$W/B2_snappy.log" 2>&1; brc=$?
stage B2/snappy "rc=$brc"; [ "$brc" -eq 0 ] || exit 32
stage B2/checkMesh START
run checkMesh -case "$B" > "$W/B2_checkMesh.log" 2>&1; brc=$?
cp "$W/B2_checkMesh.log" "$R/logs/B2_checkMesh.log"
stage B2/checkMesh "rc=$brc"; [ "$brc" -eq 0 ] && grep -q 'Mesh OK' "$W/B2_checkMesh.log" || exit 33
run python "$W/check_field_boundaries.py" "$B" > "$W/B2_boundaries.log" 2>&1; brc=$?
stage B2/boundaries "rc=$brc"; cp "$W/B2_boundaries.log" "$R/logs/B2_boundaries.log"; [ "$brc" -eq 0 ] || exit 34
# Mesh cell count is a pilot metadata field used solely to dimension beta; no preselected sample in B.
python3 "$R/update_cells.py" "$B" "$W/B2_checkMesh.log" || exit 35
# B2 stores independent returned artifacts under grade B2.
python3 "$R/harvest.py" "$B" "$R/logs" B2 >> "$R/logs/harvest_receipts.jsonl" 2>&1 & MONITOR=$!
stage B2/solve START
setsid bash "$R/launch_solve.sh" "$W" "$B" "$I" > "$B/g1_rank0.log" 2>&1 & SOLVE=$!
python3 "$R/watchdog.py" "$SOLVE" "$B" "$R/logs/B2_watchdog.txt" & WATCH=$!
wait "$SOLVE"; brc=$?; stage B2/solve "rc=$brc"
kill "$WATCH" 2>/dev/null || :; wait "$WATCH" 2>/dev/null || :; unset WATCH
kill "$MONITOR" 2>/dev/null || :; wait "$MONITOR" 2>/dev/null || :; unset MONITOR
python3 "$R/harvest.py" "$B" "$R/logs" B2 --once >> "$R/logs/harvest_receipts.jsonl" 2>&1 || :
# The measured roof y+ is emitted by the solver at terminal state; no estimate is called measured.
if [ -f "$B/g1_rank0.log" ]; then grep 'patch roof y+' "$B/g1_rank0.log" | tail -1 > "$R/logs/B2_yplus.txt" || :; fi
[ "$brc" -eq 0 ] || exit 36
if python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1]))["primal_gate"] else 1)' "$B/g1_gate.json"; then stage B2 GATE_PASS; else stage B2 GATE_FAIL; fi
stage COMPLETE OK
'''
# Trap must capture both scratch cases on failure and normal exit, not overwrite any old result.
q=q.replace('python3 "$R/harvest.py" "$C" "$R/logs" "$G" --once >> "$R/logs/harvest_receipts.jsonl" 2>&1 || :;', 'python3 "$R/harvest.py" "$C" "$R/logs" "$G" --once >> "$R/logs/harvest_receipts.jsonl" 2>&1 || :; if [ -d "${W:-/nonexistent}/cases/B2" ]; then python3 "$R/harvest.py" "$W/cases/B2" "$R/logs" B2 --once >> "$R/logs/harvest_receipts.jsonl" 2>&1 || :; fi;',1)
# B1 gate failure returns 41 and is diagnostic, not job failure; continue to B2.
q=q.replace('[ "$rc" -eq 0 ] || exit 30','[ "$rc" -eq 0 ] || [ "$rc" -eq 41 ] || exit 30')
# No B1 reconstructed output is needed; avoid potential storage increase.
(base/'b.qsub').write_text(q)
(base/'update_cells.py').write_text('''import json,re,sys\nfrom pathlib import Path\nc=Path(sys.argv[1]); t=Path(sys.argv[2]).read_text(); m=re.search(r"\\bcells:\\s*(\\d+)",t); assert m,m is not None\nn=int(m.group(1)); assert n>1000\np=c/'sample_cells.json'; j=json.loads(p.read_text()); j['mesh_cells']=n; j['cell_ids']=[0,1,2,3,4]; p.write_text(json.dumps(j)+'\\n'); print('B2 cells',n)\n''')
q=q.replace('"$R/snappyHexMeshDict_B2"; do','"$R/snappyHexMeshDict_B2" "$R/update_cells.py"; do')
(base/'b.qsub').write_text(q)
print('\n'.join(f'{p.name} {hashlib.sha256(p.read_bytes()).hexdigest()}' for p in sorted(base.glob('*')) if p.is_file()))

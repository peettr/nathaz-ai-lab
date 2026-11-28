from pathlib import Path
import shutil, hashlib
base=Path(__file__).resolve().parent
old=base.parent
src=old/'b.qsub'
assert src.is_file()
root='/groups/kareem/[用户]/L26_21_DAFOAM_20261114_B2_only'
q=src.read_text()
q=q.replace('L26_21_B_distinguish','L26_21_B2_only').replace('/groups/kareem/[用户]/L26_21_DAFOAM_20261114_B_distinguish',root).replace('h_rt=00:12:00','h_rt=02:00:00')
q=q.replace('G=coarse','G=B2')
q=q.replace('C="$W/cases/$G"','C="$W/cases/$G"')
q=q.replace('"$SRC/cases/$G/', '"$SRC/cases/coarse/')
q=q.replace('"$SRC/cases/$G/processor0"','"$SRC/cases/coarse/processor0"')
q=q.replace('cp -a "$SRC/cases/$G" "$W/cases/" || exit 86','cp -a "$SRC/cases/coarse" "$C" || exit 86')
q=q.replace('if [ -d "${W:-/nonexistent}/cases/B2" ]; then python3 "$R/harvest.py" "$W/cases/B2" "$R/logs" B2 --once >> "$R/logs/harvest_receipts.jsonl" 2>&1 || :; fi;','')
q=q[:q.index('stage empty REUSED_FROM_FIRST_G1')]+'''stage B2/source REUSED_G1_COARSE_V4
cp "$R/snappyHexMeshDict_B2" "$C/system/snappyHexMeshDict" || exit 82
[ -f "$C/system/blockMeshDict" ] && [ -f "$C/system/snappyHexMeshDict" ] || exit 82
stage B2/blockMesh START
run blockMesh -case "$C" > "$W/B2_blockMesh.log" 2>&1; brc=$?
stage B2/blockMesh "rc=$brc"; [ "$brc" -eq 0 ] || exit 31
stage B2/snappy START
run snappyHexMesh -case "$C" -overwrite > "$W/B2_snappy.log" 2>&1; brc=$?
stage B2/snappy "rc=$brc"; [ "$brc" -eq 0 ] || exit 32
stage B2/checkMesh START
run checkMesh -case "$C" > "$W/B2_checkMesh.log" 2>&1; brc=$?
cp "$W/B2_checkMesh.log" "$R/logs/B2_checkMesh.log"
stage B2/checkMesh "rc=$brc"; [ "$brc" -eq 0 ] && grep -q 'Mesh OK' "$W/B2_checkMesh.log" || exit 33
run python "$W/check_field_boundaries.py" "$C" > "$W/B2_boundaries.log" 2>&1; brc=$?
stage B2/boundaries "rc=$brc"; cp "$W/B2_boundaries.log" "$R/logs/B2_boundaries.log"; [ "$brc" -eq 0 ] || exit 34
python3 "$R/update_cells.py" "$C" "$W/B2_checkMesh.log" || exit 35
python3 "$R/harvest.py" "$C" "$R/logs" B2 >> "$R/logs/harvest_receipts.jsonl" 2>&1 & MONITOR=$!
stage B2/solve START
ulimit -f 400000
setsid bash "$R/launch_solve.sh" "$W" "$C" "$I" > "$C/g1_rank0.log" 2>&1 & SOLVE=$!
python3 "$R/watchdog.py" "$SOLVE" "$C" "$R/logs/B2_watchdog.txt" & WATCH=$!
wait "$SOLVE"; brc=$?; stage B2/solve "rc=$brc"
kill "$WATCH" 2>/dev/null || :; wait "$WATCH" 2>/dev/null || :; unset WATCH
kill "$MONITOR" 2>/dev/null || :; wait "$MONITOR" 2>/dev/null || :; unset MONITOR
python3 "$R/harvest.py" "$C" "$R/logs" B2 --once >> "$R/logs/harvest_receipts.jsonl" 2>&1 || :
if [ -f "$C/g1_rank0.log" ]; then grep 'patch roof y+' "$C/g1_rank0.log" | tail -1 > "$R/logs/B2_yplus.txt" || :; fi
[ "$brc" -eq 0 ] || [ "$brc" -eq 41 ] || exit 36
if [ ! -f "$C/g1_gate.json" ]; then stage B2 GATE_MISSING; exit 37; fi
if python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1]))["primal_gate"] else 1)' "$C/g1_gate.json"; then stage B2 GATE_PASS; else stage B2 GATE_FAIL; fi
stage COMPLETE OK
'''
# B2's chosen source is immutable coarse_v4, but the source preflight list now
# refers to coarse explicitly. Check no redundant B1 solve path remains.
assert 'stage B1' not in q and 'G=B2' in q
assert 'h_rt=02:00:00' in q
(base/'b2.qsub').write_text(q)
for f in ('rank_launcher_v5.py','launch_solve.sh','watchdog.py','harvest.py','snappyHexMeshDict_B2','update_cells.py','fvSolution'):
    shutil.copy2(old/f,base/f)
s=(old/'b_driver.py').read_text()
s=s.replace("  ratios={f:res[f][-1]/res[f][0] for f in fields} if enough else {}", "  assert len(res['p'])==3*len(res['Ux']), 'p corrector count mismatch'\n  res['p']=res['p'][0::3]\n  ratios={f:res[f][-1]/res[f][0] for f in fields} if enough else {}")
assert "res['p']=res['p'][0::3]" in s
(base/'b2_driver.py').write_text(s)
q=q.replace('"$R/b_driver.py"','"$R/b2_driver.py"').replace('cp "$R/b_driver.py" "$C/g1_driver.py"','cp "$R/b2_driver.py" "$C/g1_driver.py"')
(base/'b2.qsub').write_text(q)
print('source',src)
for p in sorted(base.iterdir()):
 if p.is_file(): print(p.name,hashlib.sha256(p.read_bytes()).hexdigest())

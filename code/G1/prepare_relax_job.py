#!/usr/bin/env python3
from pathlib import Path
import hashlib
base=Path(__file__).parent
out=base/'solve_relax'
source=(base/'solve_v5/g1_coarse_v5.qsub').read_text()
old='/groups/kareem/[用户]/L26_21_DAFOAM_20261114_G1_coarse_v5'
new='/groups/kareem/[用户]/L26_21_DAFOAM_20261114_G1_coarse_relax'
assert old in source and 'coarse_v5' in source
s=source.replace(old,new).replace('L26_21_G1_coarse_v5','L26_21_G1_coarse_relax')
s=s.replace('cp -a "$SRC/cases/$G" "$W/cases/" || exit 86','cp -a "$SRC/cases/$G" "$W/cases/" || exit 86\ncp "$R/g1_driver.py" "$C/g1_driver.py" || exit 82\ncp "$R/fvSolution" "$C/system/fvSolution" || exit 82')
s=s.replace('cp "$R/rank_launcher_v5.py" "$W/"','cp "$R/rank_launcher_v5.py" "$W/"')
start=s.index('(ulimit -f 400000; run /bin/bash -c')
end=s.index('\nrc=$?; stage "$G/solve"',start)
s=s[:start]+'''(ulimit -f 400000; setsid bash "$R/launch_solve.sh" "$W" "$C" "$I" > "$C/g1_rank0.log" 2>&1) & SOLVE=$!
python3 "$R/watchdog.py" "$SOLVE" "$C" "$R/logs/watchdog.txt" & WATCH=$!
wait "$SOLVE"''' +s[end:]
s=s.replace('kill "$MONITOR" 2>/dev/null || :; wait "$MONITOR" 2>/dev/null || :; unset MONITOR','kill "$WATCH" 2>/dev/null || :; wait "$WATCH" 2>/dev/null || :; unset WATCH\nkill "$MONITOR" 2>/dev/null || :; wait "$MONITOR" 2>/dev/null || :; unset MONITOR')
s=s.replace('python3 "$R/harvest.py" "$C"', 'python3 "$R/harvest.py" "$C"')
(out/'g1_coarse_relax.qsub').write_text(s)
h=(base/'solve_v5/harvest.py').read_text().replace("(case/'g1_rank0.log', 'rank0', False),","(case/'g1_rank0.log', 'rank0', False),\n        (case/'g1_cp_trace.csv', 'cp_trace', False),\n        (case/'g1_gate_error.txt', 'gate_error', False),")
(out/'harvest.py').write_text(h)
for name in ['g1_coarse_relax.qsub','harvest.py','g1_driver.py','fvSolution','launch_solve.sh','watchdog.py']:
 p=out/name;print(name,hashlib.sha256(p.read_bytes()).hexdigest())

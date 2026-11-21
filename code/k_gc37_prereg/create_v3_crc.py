"""Create v3 CRC validation and two UGE wrappers from tested v2 analogues."""
from pathlib import Path
b=Path('./23_AI_Weather/06_Logs/k_gc37_preflight')
r=Path(__file__).resolve().parent
src=(b/'validate_gc37_wps_delivery_v2.py').read_text()
s=src.replace('drivers_gc37_v2','drivers_gc37_v3').replace('ops_cpu_v2','ops_cpu_v3').replace('READBACK_GC37_V2','READBACK_GC37_V3')
s=s.replace("field not in ('PMSL','SPECHUMD')", "field not in ('PMSL','SPECHUMD','TT','UU','VV')")
s=s.replace("'all level>=200000 except PMSL and SPECHUMD (Q2) compared as exact binary slabs'", "'all level>=200000 except PMSL, SPECHUMD (Q2), TT (T2), UU (U10), VV (V10) compared as exact binary slabs; t0 shared; forecast near-surface arm-specific'")
s=s.replace("==15", "==12").replace("'shared_surface_fields':15", "'shared_surface_fields':12")
s=s.replace("assert (OPS/'run.exitcode').read_text().strip()=='0'", "assert (OPS/'run_p24.exitcode').read_text().strip()=='0' and (OPS/'run_p48p72.exitcode').read_text().strip()=='0'")
p=r/'validate_gc37_wps_delivery_v3.py';assert not p.exists();p.write_text(s)
for tag,cycles in [('p24',['2020060806']),('p48p72',['2020060706','2020060606'])]:
    root='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/drivers_gc37_v3/ops_cpu_v3'
    lines=['#!/bin/bash',f'#$ -N gc37v3{tag}','#$ -cwd','#$ -q long','#$ -pe smp 4','#$ -l h_rt=04:00:00','#$ -l m_mem_free=8G','#$ -l h=!d24cepyc154.超算&!d24cepyc161.超算&!d24cepyc162.超算',f'#$ -o {root}/uge_{tag}.out',f'#$ -e {root}/uge_{tag}.err',f'ROOT={root}','cd "$ROOT" || exit 90','export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1','module load python/3.12.15 || exit 91', '''"$ROOT/.venv/bin/python" -c 'import numpy,scipy,pygrib; print("IMPORT_OK")' || exit 92''', 'rc=0']
    for cycle in cycles:
        lines += [f'if [ "$rc" -eq 0 ]; then "$ROOT/.venv/bin/python" -u "$ROOT/build_gc37_wps_crc_cpu_v3.py" --cycle {cycle} > "$ROOT/wps_{cycle}.log" 2>&1; rc=$?; fi']
    lines += [f'printf "%s\\n" "$rc" > "$ROOT/run_{tag}.exitcode"','exit "$rc"']
    p=r/f'submit_gc37_wps_{tag}_v3.sh';assert not p.exists();p.write_text('\n'.join(lines)+'\n')
print('created v3 validator and UGE scripts')

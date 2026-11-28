from pathlib import Path
import hashlib
r=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')
p=r/'inputs_2024_R1R2_v1'
o=p/'ops_rest_v2'
print('OPS',o.exists(),[(x.name,x.stat().st_size) for x in o.iterdir()] if o.exists() else [])
print('DRIVER_OPS',[(ev,cy,(r/f'drivers_gc37_{ev}_v1'/f'ops_input_{cy}_v2').is_dir()) for ev,cy in [('R1','2024073100'),('R1','2024073000'),('R1','2024072900'),('R2','2024060218'),('R2','2024060118')]])
print('RAWS',[(x.name,len(list(x.iterdir()))) for x in (p/'raw').iterdir()])
print('HASH',[(n,hashlib.sha256((p/n).read_bytes()).hexdigest()) for n in ['run_crc_inputs_r1r2_v2.py','build_gc37_wps_crc_cpu_r1r2_v2.py','prepare_gc37_gfs_2024_r1r2_v2.py']])
print('SCRIPTS',[(x.name,x.exists()) for x in [o/'submit_rest_v2.sh',p/'event_times_gc37.json',p/'domain_bbox_gc37.json']])
t=r/'drivers_gc37_R2_v1/ops_input_2024060318_v2'
print('PILOT_OPS',[(x.name,x.stat().st_size) for x in t.iterdir()])
print('COMMON', (t/'COMMON_LEVELS.txt').read_text() if (t/'COMMON_LEVELS.txt').exists() else 'missing')

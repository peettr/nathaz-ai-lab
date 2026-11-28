from pathlib import Path
import shutil
base=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
ops=base/'drivers_N9_v1/ops_N9_72h_GFS_b2'
inf=base/'infer_b2_N9_72h_v1'
assert not ops.exists() and not inf.exists(), 'staging roots already exist; inspect first'
ops.mkdir(parents=True)
inf.mkdir(parents=True)
src=base/'drivers_N9_v1/ops_N9_48h_GFS_b2'
for name in ('build_gc37x_wps_gfs_b2.py','wps_format5.py','COMMON_LEVELS.txt','event_times_bbox_gc37x.json'):
    shutil.copy2(src/name,ops/name)
    assert (ops/name).is_file()
script=(src/'submit_N9_48h_GFS_b2.sh').read_text().replace('N9_48h_GFS_b2','N9_72h_GFS_b2').replace('N9_48_GFS','N9_72_GFS').replace('GC37_LEAD=48','GC37_LEAD=72').replace('2022060806','2022060706').replace('infer_b2_N9_48h_v1','infer_b2_N9_72h_v1')
assert '2022060806' not in script and '48h_GFS_b2' not in script
(ops/'submit_N9_72h_GFS_b2.sh').write_text(script)
(src/'submit_N9_48h_GFS_b2.sh').stat()
old=base/'infer_b2_N9_48h_v1'
for name in ('check_gc37x_inputs_v2.py','graphcast_source','venv','weights'):
    target=(old/name).resolve(strict=True)
    (inf/name).symlink_to(target)
for name in ('event_times_bbox_gc37x.json','infer_b2_science_v1.py','run_single_b2_v1.py'):
    shutil.copy2(old/name,inf/name)
for name in ('gates','raw'):
    (inf/name).mkdir()
for name,source in (('run_b2.sh','N9_72h_run.sh'),('N9_72h.sub','N9_72h.sub')):
    if source=='N9_72h_run.sh':
        text=(old/'run_b2.sh').read_text().replace('infer_b2_N9_48h_v1','infer_b2_N9_72h_v1').replace('--lead 48h','--lead 72h')
    else:
        text=(old/'N9_48h.sub').read_text().replace('infer_b2_N9_48h_v1','infer_b2_N9_72h_v1').replace('N9_48h','N9_72h')
    (inf/name).write_text(text)
print('STAGED',ops,inf)

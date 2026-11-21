from pathlib import Path
import shutil, hashlib
base=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')
root=base/'inputs_2024_R1R2_v1'
assert not (root/'ops_rest_v2').exists()
cycles=[('R1','2024073100'),('R1','2024073000'),('R1','2024072900'),('R2','2024060218'),('R2','2024060118')]
pilot=base/'drivers_gc37_R2_v1/ops_input_2024060318_v2'
assert (pilot/'COMMON_LEVELS.txt').is_file()
assert (root/'raw').is_dir()
assert all(not (base/f'drivers_gc37_{event}_v1'/f'ops_input_{cycle}_v2').exists() for event,cycle in cycles)
(root/'ops_rest_v2').mkdir()
for event,cycle in cycles:
    ops=base/f'drivers_gc37_{event}_v1'/f'ops_input_{cycle}_v2'
    ops.mkdir(parents=True)
    for name in ('COMMON_LEVELS.txt','event_times_gc37.json','domain_bbox_gc37.json'):
        source=(pilot/name) if name=='COMMON_LEVELS.txt' else (root/name)
        with (ops/name).open('xb') as dest:
            dest.write(source.read_bytes())
        assert hashlib.sha256((ops/name).read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest()
    print('STAGED',event,cycle,ops)
print('ROOT',root/'ops_rest_v2')

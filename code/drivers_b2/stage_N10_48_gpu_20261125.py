from pathlib import Path
import os

base = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
src = base/'infer_b2_N8_48h_v1'
dst = base/'infer_b2_N10_48h_v1'
assert not dst.exists(), dst
assert (base/'inputs_N8N9N10_v1/input_2024050200_zero.nc').is_file()
dst.mkdir()
for name in ('check_gc37x_inputs_v2.py', 'graphcast_source', 'venv', 'weights'):
    target = (src/name).resolve(strict=True)
    (dst/name).symlink_to(target)
for name in ('event_times_bbox_gc37x.json', 'run_single_b2_v1.py', 'infer_b2_science_v1.py'):
    (dst/name).write_bytes((src/name).read_bytes())
for name in ('run_b2.sh', 'N8_48h.sub'):
    text = (src/name).read_text().replace('N8_48h', 'N10_48h').replace('--event N8', '--event N10')
    out = dst/('N10_48h.sub' if name.endswith('.sub') else name)
    assert not out.exists()
    out.write_text(text)
(dst/'run_b2.sh').chmod(0o755)
(dst/'gates').mkdir()
(dst/'raw').mkdir()
for name in ('run_b2.sh', 'N10_48h.sub', 'gates', 'raw', 'venv', 'weights', 'graphcast_source', 'event_times_bbox_gc37x.json', 'run_single_b2_v1.py', 'infer_b2_science_v1.py', 'check_gc37x_inputs_v2.py'):
    assert (dst/name).exists(), name
print(dst)

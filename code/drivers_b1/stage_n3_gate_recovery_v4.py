#!/usr/bin/env python3
"""Stage only N3 24/48h after missing gates directory failure; no submit."""
from pathlib import Path
import shutil

base = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
for lead in ('24', '48'):
    old = base / f'infer_b1_blackwell_recover_N3_{lead}_v3'
    new = base / f'infer_b1_blackwell_recover_N3_{lead}_v4'
    assert old.is_dir() and not new.exists(), (old, new)
    assert (old / 'infer.exitcode').read_text().strip() == '107'
    new.mkdir()
    for name in ('check_gc37x_inputs_v2.py', 'event_times_bbox_gc37x.json', 'graphcast_source', 'venv', 'weights'):
        source = old / name
        assert source.is_symlink(), source
        (new / name).symlink_to(source.resolve())
    for name in ('resume_single_blackwell_b1_v3.py',):
        shutil.copy2(old / name, new / name)
    for pattern in (f'run_recover_N3_{lead}_v3.sh', f'recover_N3_{lead}_v3.sub'):
        content = (old / pattern).read_text()
        assert str(old) in content, pattern
        content = content.replace(str(old), str(new))
        out = new / pattern.replace('_v3.', '_v4.')
        out.write_text(content.replace(pattern, out.name))
        out.chmod(0o755)
    (new / 'gates').mkdir()
    print(new)

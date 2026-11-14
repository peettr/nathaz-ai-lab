import subprocess,sys
from pathlib import Path
root=Path('/content/v6_work')
sanity=__import__('json').loads((root/'sanity/segment_summary.json').read_text())
assert 0.75 <= sanity['total_median_r2'] <= 0.80
assert not (root/'group').exists()
assert (root/'group_manifest.json').exists()
out=root/'group'; out.mkdir()
with (out/'launcher.log').open('w') as f:
    proc=subprocess.Popen([sys.executable,'-u',str(root/'v6_group_importfix_bootstrap.py')],cwd=str(root),stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
(out/'pid').write_text(str(proc.pid))
print('GROUP_STARTED',proc.pid,flush=True)

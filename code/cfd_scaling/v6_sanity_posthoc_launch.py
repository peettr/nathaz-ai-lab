import subprocess,sys
from pathlib import Path
p=Path('/content/v6_work/sanity')
assert (p/'FAILED').exists() and (p/'checkpoint_ep1000.pt').exists()
assert not (p/'posthoc.pid').exists() and not (p/'segment_summary.json').exists()
log=(p/'posthoc.log').open('w')
proc=subprocess.Popen([sys.executable,'-u','/content/v6_work/v6_sanity_posthoc_importfix.py'],stdout=log,stderr=subprocess.STDOUT,cwd='/content/v6_work',start_new_session=True)
(p/'posthoc.pid').write_text(str(proc.pid))
print('POSTHOC_STARTED',proc.pid,flush=True)

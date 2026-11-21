import os, subprocess,sys
from pathlib import Path
root=Path('/content/v6_work')
segment=os.environ.get('V6_SEGMENT','sanity')
assert segment in ('sanity','group')
assert (root/'v6_legacy_code/all_data.pt').stat().st_size==4321275076
out=root/segment
assert not out.exists(), 'segment already started: '+str(out)
out.mkdir()
log=(out/'launcher.log').open('w')
p=subprocess.Popen([sys.executable,'-u',str(root/'v6_run_segment.py'),'--segment',segment],cwd=str(root),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(out/'pid').write_text(str(p.pid))
print('LAUNCHED',segment,p.pid,flush=True)

import os, subprocess, pathlib, hashlib
r=pathlib.Path('/content')
expected='4f155aabbcbad40ee40cc1ee518e4dc2f1e82f9452a8a931099ab723477edeeb'
p=r/'r2_conus_main.jsonl'
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected, 'checkpoint SHA mismatch'
assert len(p.read_text().splitlines())==230
assert not (r/'r2_segment_b.done').exists()
assert not (r/'segment_b3_launch_v2.start').exists()
assert len((r/'segment_b_manifest.csv').read_text().splitlines())==19
assert (r/'continue_v1_a.py').exists() and (r/'continue_conus_b.py').exists()
(r/'segment_b3_launch_v2.start').open('x').write(str(os.getpid()))
log=(r/'segment_b3.log').open('x')
proc=subprocess.Popen(['python','-u','/content/continue_conus_b.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd='/content')
print('B3_PID',proc.pid,'SOURCE_SHA',expected,flush=True)

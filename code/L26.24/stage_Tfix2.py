from pathlib import Path
import shutil, hashlib
old=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix')
new=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix2')
assert not new.exists()
new.mkdir()
files=['baseline_B1_worker.py','baseline_B2_worker.py','l1b_cpu.py','l1_timing_original.csv','libic0_B2.so']
for name in files:
    shutil.copyfile(old/name,new/name)
src=(old/'tfix_worker.py').read_text()
assert src.count('assert set(NAMES)==set(old)')==1
assert src.count("ROOT = Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix')")==1
src=src.replace('assert set(NAMES)==set(old)','assert set(NAMES)<=set(old)')
src=src.replace("ROOT = Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix')", "ROOT = Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix2')")
(new/'tfix2_worker.py').write_text(src)
src=(old/'job_Tfix.sh').read_text()
assert src.count('/L26_24_LINSYS_20261115_L1/Tfix')==1
src=src.replace('/L26_24_LINSYS_20261115_L1/Tfix','/L26_24_LINSYS_20261115_L1/Tfix2').replace('L2624_Tfix','L2624_Tfix2').replace('tfix_worker.py','tfix2_worker.py')
(new/'job_Tfix2.sh').write_text(src)
for p in sorted(new.iterdir()):
    print(p.name, hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size)

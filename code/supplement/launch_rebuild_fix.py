from pathlib import Path
import subprocess, importlib.util
p=Path('/content/m6')
assert (p/'rebuild_gfs.exit').read_text().strip()=='1'
assert len(list((p/'test_gfs').glob('*.csv')))==350
assert importlib.util.find_spec('eccodes')
assert not (p/'rebuild_gfs_fix.launch').exists()
(p/'rebuild_gfs_fix.launch').open('x').write('dependency eccodes installed; resume missing inits only')
cmd='cd /content/m6; python -u m6_extract.py test > rebuild_gfs_fix.log 2>&1; echo $? > rebuild_gfs_fix.exit; touch rebuild_gfs_fix.done'
a=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('PID',a.pid)

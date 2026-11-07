from pathlib import Path
import tarfile, hashlib, subprocess, sys
p=Path('/content/m6');p.mkdir(exist_ok=True)
for fname,dirname in [('obs_source_20261028.tgz','obs'),('test_checkpoint_1028_181649.tgz','test_gfs')]:
    with tarfile.open(p/fname) as t:
        members=t.getmembers()
        assert all((m.isfile() or m.isdir()) and (m.name==dirname or m.name.startswith(dirname+'/')) and '..' not in Path(m.name).parts for m in members)
        expected={Path(m.name).name for m in members if m.isfile()}
        if (p/dirname).exists():
            assert {x.name for x in (p/dirname).glob('*.csv')}==expected
        else:t.extractall(p,filter='data')
print('EXTRACTED',len(list((p/'obs').glob('*.csv'))),len(list((p/'test_gfs').glob('*.csv'))),flush=True)
assert len(list((p/'obs').glob('*.csv')))==12
assert len(list((p/'test_gfs').glob('*.csv')))==350
assert hashlib.sha256((p/'m6_score.py').read_bytes()).hexdigest()=='11c7f845a502406d7232c67c2308fdca51d199d55d5d71c52f95448ce66ea39c'
assert len(list(p.glob('train_pairs_delay*.parquet')))==3
assert (p/'models.json').exists()
command='cd /content/m6; python -u m6_extract.py test > rebuild_gfs.log 2>&1; echo $? > rebuild_gfs.exit; touch rebuild_gfs.done'
proc=subprocess.Popen(['bash','-lc',command],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('STARTED',proc.pid,flush=True)

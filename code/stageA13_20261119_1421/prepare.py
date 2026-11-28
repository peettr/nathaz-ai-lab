from pathlib import Path
import shutil,tarfile
here=Path(__file__).resolve().parent
prev=here.parent/'stageA12_20261119_133203'
with tarfile.open(prev/'t17_stage.tar.gz') as f:
    names=f.getnames()
    assert all((n=='pack_stage' or n.startswith('pack_stage/')) and '..' not in Path(n).parts for n in names)
    f.extractall(here/'work',filter='data')
for name in ('worker_full.py','controller_full.py','remote_io.py','assert_ledger.py','machine.py','stub_solver.py'):
    shutil.copy2(prev/name,here/name)
print('copied',len(names),'members')

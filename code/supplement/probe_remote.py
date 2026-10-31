from pathlib import Path
import subprocess
p=Path('/content/m6')
print('csv_count',len(list((p/'test_gfs').glob('*.csv'))),'done',(p/'rebuild_gfs.done').exists(),'exit',(p/'rebuild_gfs.exit').read_text().strip() if (p/'rebuild_gfs.exit').exists() else None)
print('log_tail','\n'.join((p/'rebuild_gfs.log').read_text().splitlines()[-8:]))
print('processes',subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout.split('m6_extract.py')[:1][-1][-1000:])

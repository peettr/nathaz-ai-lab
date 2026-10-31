from pathlib import Path
p=Path('/content/m6')
for name in ('rebuild_gfs_fix','score_rebuilt','rebuild_core','postreview'):
    log=p/f'{name}.log'; done=p/f'{name}.done'; exit=p/f'{name}.exit'
    print(name,'done',done.exists(),'exit',exit.read_text().strip() if exit.exists() else None,'tail',' / '.join(log.read_text().splitlines()[-5:]) if log.exists() else 'none')
print('GFS_COUNT',len(list((p/'test_gfs').glob('*.csv'))))

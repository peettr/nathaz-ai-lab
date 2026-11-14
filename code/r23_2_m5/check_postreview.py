from pathlib import Path
p=Path('/content/m5');print('exit', (p/'postreview.exit').read_text() if (p/'postreview.exit').exists() else 'running');print((p/'postreview.log').read_text()[-4000:] if (p/'postreview.log').exists() else 'no log')

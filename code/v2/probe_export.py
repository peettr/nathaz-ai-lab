from pathlib import Path
import os
p=Path('/content/l2613v2_export.log')
print(p.read_text()[-3000:] if p.exists() else 'NO LOG')
for f in Path('/content/l2613v2').glob('*corrected*'):print(f.name,f.stat().st_size)
print('done',(Path('/content/l2613v2/stl_export_corrected.done')).exists())

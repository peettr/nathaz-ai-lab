from pathlib import Path
import json
r=Path('/content/r234c_gc37_E2E3')
print('done', (r/'infer_crc_inputs_resume_v3.done').exists(), 'failed', (r/'infer_crc_inputs_resume_v3.failed').exists())
for p in sorted(r.glob('forecast_*')):
 print(p.name, [(x.name,x.stat().st_size) for x in p.iterdir() if x.suffix!='.npz'])
for p in sorted(r.glob('infer_*.log')):
 print('LOG',p.name,p.stat().st_size,p.read_text()[-250:])

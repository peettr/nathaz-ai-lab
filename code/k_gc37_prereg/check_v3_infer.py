from pathlib import Path
r=Path('/content/r234c_gc37_v3')
for n in ['infer_gc37_v3.log','stage_gc37_weights_v3.log','prepare_2020060806.log','infer_2020060806.log','infer_gc37_v3.failed']:
 p=r/n
 print(n, 'missing' if not p.exists() else p.read_text(errors='replace')[-1100:])
print('manifest_names',[x.name for x in r.glob('RAW_MANIFEST_*')])

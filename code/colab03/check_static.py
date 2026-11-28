from pathlib import Path
p=Path('/content/l264a100/texas');f=p/'build_static_retry.log';print('STATIC',f.exists(),f.read_text()[-4000:] if f.exists() else '',flush=True)
print('DONE',(p/'build_static.done').exists(),'FAST',(Path('/content/l264a100/fast_data/fast.done')).exists(),flush=True)

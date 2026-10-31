# Inspect the remote initialization log and flag export state.
from pathlib import Path
p=Path('/content/step4_init/init.log');print('LOG',p.stat().st_size if p.exists() else 0);print('\n'.join(p.read_text(errors='replace').splitlines()[-35:]) if p.exists() else '')
f=Path('/content/step4_init/case/RESULTS/native_flags_z0_90.bin');print('FLAGS',f.exists(),f.stat().st_size if f.exists() else 0)

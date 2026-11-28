from pathlib import Path
import numpy as np
p=Path('/content/luw_city_ma010_v2_1016/case/RESULTS/native_flags_z0_62.bin')
print('native flags:',p.exists(),p.stat().st_size if p.exists() else None)
if p.exists():
 a=np.fromfile(p,dtype=np.uint8)
 assert a.size==63*500*500,a.size
 target=Path('/content/ma010_flags_z0_62.npz')
 np.savez_compressed(target,flags=a.reshape(63,500,500))
 print('compressed',target.stat().st_size)

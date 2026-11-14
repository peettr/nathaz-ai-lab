import trimesh
from pathlib import Path
p=Path('/content/l2613v2')
for src in ('OpenStreetMap','Overture'):
 m=trimesh.load(p/f'{src}_1m_ground0.stl',force='mesh',process=True)
 print(src,'processed watertight',m.is_watertight,'euler',m.euler_number,'vertices',len(m.vertices),flush=True)

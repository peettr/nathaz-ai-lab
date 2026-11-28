from pathlib import Path
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import trimesh,numpy as np
R=Path('/content/qtl_l2630_step1a/selected')
for tag in ('ROI','Surrounding'):
 m=trimesh.load_mesh(str(R/(tag+'.stl')),process=False)
 fig=plt.figure(figsize=(9,7));ax=fig.add_subplot(projection='3d')
 faces=m.triangles; step=max(1,len(faces)//5000)
 coll=Poly3DCollection(faces[::step],alpha=.85,linewidths=.05,edgecolors='#173348',facecolor='#58a8cf')
 ax.add_collection3d(coll)
 lo,hi=m.bounds
 ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_zlim(0,min(max(hi[2],1),150))
 ax.set_box_aspect((1,1,.22));ax.view_init(elev=26,azim=-68)
 ax.set(xlabel='UTM x (m)',ylabel='UTM y (m)',zlabel='height (m)',title=tag+' | USA Structures extruded STL')
 fig.tight_layout();out=R/(tag+'_STL_3d_v2.png');assert not out.exists();fig.savefig(out,dpi=130);plt.close(fig)
 print(tag,len(m.faces),len(faces[::step]),out,flush=True)

"""Audit native 22-plane mask; upper-domain connectivity remains conditional."""
from pathlib import Path
import numpy as np,json
from scipy import ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
f=np.load(R/'stage3_native_flags.npz')['flags']
assert f.shape==(22,500,500)
solid=(f&1)!=0;equil=(f&2)!=0; fluid=~solid&~equil; passable=~solid
layers=[dict(z=z,solid=int(solid[z].sum()),equilibrium=int((equil[z]&~solid[z]).sum()),fluid=int(fluid[z].sum())) for z in range(22)]
labels,n=ndimage.label(passable,structure=ndimage.generate_binary_structure(3,1))
count=np.bincount(labels.ravel())
# 'inlet' is west x=0 with profile boundary; other open faces are tracked separately.
inlet_ids=np.unique(labels[:,:,0][passable[:,:,0]]);inlet_ids=inlet_ids[inlet_ids>0]
top_ids=np.unique(labels[21][passable[21]]);top_ids=top_ids[top_ids>0]
connected=np.isin(labels,inlet_ids)
other=fluid&~connected
origin=(1,143,133);origin_id=int(labels[origin]);origin_fluid=bool(fluid[origin]);near=[]
for dz in (-1,0,1):
 for dy in (-1,0,1):
  for dx in (-1,0,1):
   if not (dz or dy or dx):continue
   z,y,x=np.array(origin)+np.array((dz,dy,dx))
   if 0<=z<22 and 0<=y<500 and 0<=x<500 and fluid[z,y,x]:near.append({'xyz':[int(x),int(y),int(z)],'inlet_connected_within_22':bool(connected[z,y,x]),'component':int(labels[z,y,x])})
result={'shape_zyx':list(f.shape),'layers':layers,'components_in_22':int(n),'inlet_component_ids':inlet_ids.tolist(),'top_component_ids':top_ids.tolist(),'fluid_not_connected_to_west_within_22':int(other.sum()),'fluid_not_connected_to_west_below_20':int(other[:21].sum()),'origin_xyz':[133,143,1],'origin_flag':int(f[origin]),'origin_fluid':origin_fluid,'origin_component':origin_id,'origin_connected_to_west_within_22':bool(connected[origin]),'origin_component_touches_top_z21':bool(origin_id in top_ids),'origin_component_size_22':int(count[origin_id]),'origin_eight_fluid_neighbors':near,'limitation':'Only z=0..21 exported. Other components touching z21 might connect to west via z>=22; truly sealed components require not touching z21 nor lateral/east open faces.'}
(R/'stage3_cavity_audit.json').write_text(json.dumps(result,indent=2)+'\n')
plt.figure(figsize=(8,8));plt.imshow(other[:21].any(axis=0),origin='lower',cmap='gray_r');plt.scatter([133],[143],c='red',s=35);plt.title('Fluid not west-connected in native z=0..20 slice; red=R1');plt.xlabel('x');plt.ylabel('y');plt.tight_layout();plt.savefig(R/'stage3_cavity_map.png',dpi=140);plt.close()
print(json.dumps({k:v for k,v in result.items() if k not in ('layers','origin_eight_fluid_neighbors')},indent=2))
print('neighbors',near)
print('layers',layers)

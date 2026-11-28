import json, numpy as np, geopandas as gpd, pandas as pd
from pathlib import Path
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
src=Path('/content/qtl_l2630_step1a/selected/ROI_heights.geojson');r=Path('/content/qtl_l2630_step1b/chicago_USA');r.mkdir(exist_ok=False)
frame=gpd.read_file(src).to_crs(32616);cx,cy=Transformer.from_crs(4326,32616,always_xy=True).transform(-87.6378,41.8988);xmin=cx-250;ymax=cy+250
shapes=[(g,float(h)) for g,h in zip(frame.geometry,frame.buildingheight) if not g.is_empty and np.isfinite(h) and 0<float(h)<132]
h=rasterize(shapes,out_shape=(500,500),transform=from_origin(xmin,ymax,1,1),fill=0,dtype='float32',all_touched=False)
np.savetxt(r/'palm_height_1m.asc',h,fmt='%.3f',header='PALM ASCII 2.5D; 500 rows north-to-south x 500 columns east; dx=dy=1 m; flip_y on import; x=UTM east (assumed wind direction); periodic horizontal',comments='# ')
fig,ax=plt.subplots(figsize=(7,7));im=ax.imshow(h,origin='upper');fig.colorbar(im,ax=ax,label='height [m]');ax.set_title('Chicago USA 1m height | source: USA Structures CC BY 4.0');fig.tight_layout();fig.savefig(r/'height_grid.png',dpi=150);plt.close(fig)
info={'grid_shape':[500,500],'dx_m':1,'height_min':float(h.min()),'height_max':float(h.max()),'occupied_cells':int(np.count_nonzero(h)),'solid_voxels':int(np.floor(h[h>0]+.5).astype(int).sum()),'missing_height_cells':int(np.count_nonzero((h>0)&(~np.isfinite(h)))),'source':'USA Structures CC BY 4.0; source file '+str(src),'manual_edits':0,'x_alignment':'UTM east, inflow direction unverified','flip_y':'north row first; consumer flip_y','horizontal_periodic':'requires R21.7 boundary configuration; no actual consumer import'}
(r/'metrics.json').write_text(json.dumps(info,indent=2));(r/'worker.done').write_text('ok');print(info,flush=True)

import importlib.util
for x in ['rasterio','pyproj','affine','onnxruntime','scipy']:
 print(x,bool(importlib.util.find_spec(x)))
p='/content/e_terrain/wn_pilot/cha_dem_143_1_90m_vel.asc'
with open(p) as f:
 for i in range(7):print(f.readline()[:160].strip())

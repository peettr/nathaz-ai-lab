import rasterio,pyproj,numpy as np,csv
p='/content/e_terrain/wn_pilot/cha_dem_143_1_90m_vel.asc'
x,y=pyproj.Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True).transform(7.054367,47.131761)
with rasterio.open(p) as d:
 print('station',x,y,'bounds',d.bounds,'sample',list(d.sample([(x,y)])),'shape',d.shape,'cellsize',d.res)

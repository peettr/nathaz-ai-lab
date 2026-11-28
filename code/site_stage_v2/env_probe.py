import importlib.util
for x in ('geopandas','shapely','fiona','xarray','gcsfs','zarr','scipy','pyproj','cartopy'):
 print(x,bool(importlib.util.find_spec(x)),flush=True)

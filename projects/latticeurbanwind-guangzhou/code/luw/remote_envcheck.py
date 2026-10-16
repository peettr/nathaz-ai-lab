import subprocess
for c in [['python3','--version'],['which','uv'],['python3','-m','pip','--version'],['/content/luw-aij/repo/.venv/bin/python','-m','pip','--version']]:
 p=subprocess.run(c,capture_output=True,text=True); print(c,p.returncode,p.stdout[-500:],p.stderr[-500:])
for name in ['numpy','scipy','pandas','xarray','netCDF4','dask','pyproj','shapely','geopandas','fiona','rtree','matplotlib','numba','vtk','pyvista','trimesh','mapbox_earcut','triangle','pyopencl','cuda','rasterio','manifold3d']:
 p=subprocess.run(['python3','-c',f'import {name}'],capture_output=True,text=True); print(name,p.returncode,p.stderr[-150:] if p.returncode else '')

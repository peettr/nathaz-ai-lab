import os,glob,subprocess
for p in ['/content/e_terrain/wn_env/share/proj','/content/e_terrain/wn_env/share/proj/proj.db','/usr/share/proj/proj.db']:
 print(p,os.path.exists(p),os.path.isdir(p),os.path.getsize(p) if os.path.isfile(p) else None)
print('env',[(k,v) for k,v in os.environ.items() if 'PROJ' in k or 'GDAL' in k])
print('which',subprocess.run(['/content/e_terrain/wn_env/bin/projinfo','EPSG:32632'],capture_output=True,text=True).stderr[:1000])

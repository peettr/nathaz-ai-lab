import zipfile,glob
with zipfile.ZipFile('/content/e_terrain_obs.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
 for p in glob.glob('/content/e_terrain/*.csv')+glob.glob('/content/e_terrain/*.json'):
  z.write(p,arcname=p.split('/')[-1])
print('ARCHIVED',len(z.namelist()))

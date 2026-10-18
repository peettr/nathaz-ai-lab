import shutil,subprocess,glob,os,time
for s in ['WindNinja','windninja','micromamba','conda','mamba','gdal_translate','apt-get']:
 print(s,shutil.which(s))
p='/content/e_terrain/full/forecast_parts'
files=glob.glob(p+'/*.csv');errors=glob.glob(p+'/ERROR_*.txt')
print('progress',len(files),len(errors),'alive',os.path.exists('/proc/'+open('/content/e_terrain/forecast_pid').read().strip()))
print('log_tail','\n'.join(open('/content/e_terrain/full_forecast.log').read().splitlines()[-6:]))

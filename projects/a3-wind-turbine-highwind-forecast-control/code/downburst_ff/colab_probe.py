import os,sys,subprocess,shutil
print('cores',os.cpu_count(),'memory',open('/proc/meminfo').readline(),'python',sys.version,'disk',shutil.disk_usage('/content'))
for x in ('numpy','scipy','matplotlib'):
 try:
  m=__import__(x);print(x,m.__version__)
 except Exception as e:print(x,repr(e))
for x in ('conda','micromamba','openfast','gfortran','cmake'):
 print(x,shutil.which(x))

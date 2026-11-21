import shutil,subprocess,sys
print(sys.version)
for name in ('python3.12','python3.11','uv','micromamba'):
 print(name,shutil.which(name))

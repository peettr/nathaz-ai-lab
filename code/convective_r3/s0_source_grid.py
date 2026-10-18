import pathlib,re
for name in ('stormcast','stormcastconus'):
 p=pathlib.Path('/usr/local/lib/python3.13/dist-packages/earth2studio/models/px/'+name+'.py')
 s=p.read_text().splitlines()
 for i,line in enumerate(s):
  if re.search(r'lat|lon|1059|1024|1792|512|640|slice\(',line,re.I):
   if 50<i<550:print(name,i+1,line[:180])

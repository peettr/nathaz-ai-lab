import zipfile,collections,re,statistics
p='/content/zenodo19041698/attempt3/boundaryData.zip'
with zipfile.ZipFile(p) as z:
 names=z.namelist()
 files=[x for x in names if not x.endswith('/')]
 print('files',len(files),'basenames',collections.Counter(x.rsplit('/',1)[-1] for x in files))
 for x in files:
  if 'points' in x.lower() or 'readme' in x.lower() or 'info' in x.lower():
   print('special',x,z.getinfo(x).file_size);print(z.read(x)[:1000].decode(errors='replace'))
 ts=sorted((float(x.split('/')[1]),x) for x in files if x.endswith('/U'))
 print('TIME',len(ts),ts[:6],ts[-6:]);dt=[round(ts[i+1][0]-ts[i][0],9) for i in range(len(ts)-1)];print('DT',collections.Counter(dt).most_common(10))
 for i in [0,len(ts)//2,len(ts)-1]:
  print('FRAME',ts[i]);print(z.read(ts[i][1])[:650].decode(errors='replace'))

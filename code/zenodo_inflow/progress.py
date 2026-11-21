import os
r='/content/zenodo19041698/attempt3'
for name in ('boundaryData.zip','download.log','download.done','zip_listing.json'):
 p=r+'/'+name
 print(name,os.path.getsize(p) if os.path.exists(p) else 'missing')
 if name=='download.log' and os.path.exists(p):print(open(p).read()[-1000:])

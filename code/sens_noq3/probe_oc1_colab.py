import urllib.request,gzip,re
u='https://www.ncei.noaa.gov/pub/data/noaa/2011/722350-03940-2011.gz';r=gzip.decompress(urllib.request.urlopen(u,timeout=25).read()).decode('latin-1');a=[x for x in r.splitlines() if x[15:27]=='201101010354'];print('ROWS',len(a));
for x in a:print('RECORD',x[:110],'OC1',x.find('OC1'),x[x.find('OC1'):x.find('OC1')+15],'REM',x[x.find('REM'):x.find('REM')+160])

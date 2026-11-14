import urllib.request,gzip,tarfile,json
url='https://www.ncei.noaa.gov/pub/data/noaa/2015/72551014939-2015.gz'
try:
 b=gzip.decompress(urllib.request.urlopen(url,timeout=25).read()).decode('latin-1');r=[x for x in b.splitlines() if x[15:27]=='201501081154'];print('RAWS',len(r));
 for x in r:print('RAW',x[:120],x.find('OC1'),x[x.find('OC1')-15:x.find('OC1')+22],x[x.find('REM'):x.find('REM')+190])
except Exception as e:print('ERR',repr(e))

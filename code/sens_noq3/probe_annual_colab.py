import urllib.request,gzip
u='https://www.ncei.noaa.gov/pub/data/noaa/2011/724400-13995-2011.gz'
b=urllib.request.urlopen(u,timeout=30).read();print('annual_bytes',len(b));r=gzip.decompress(b).decode('latin-1').splitlines();a=[x for x in r if x[15:23]=='20111223'];print('rows_day',len(a));
for x in a[:5]:print('ROW',x[:110],x[105:180],x[x.find('REM'):x.find('REM')+180])

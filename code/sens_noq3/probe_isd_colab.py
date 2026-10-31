import urllib.request,time
for u in ['https://www.ncei.noaa.gov/pub/data/noaa/2011/724400-13995-2011.gz','https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations=72440013995&startDate=2011-12-23&endDate=2011-12-23&format=json&includeAttributes=true']:
 try:
  z=urllib.request.urlopen(urllib.request.Request(u,headers={'Range':'bytes=0-1023'}),timeout=12)
  print(u,z.status,len(z.read(1024)))
 except Exception as e:print(u,repr(e))

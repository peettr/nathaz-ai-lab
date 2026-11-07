import urllib.request
u='https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20240401/conus/hrrr.t00z.wrfprsf00.grib2.idx'
s=urllib.request.urlopen(u,timeout=30).read().decode().splitlines()
for line in s:
 if any(':'.join(line.split(':')[3:5])==f'{var}:{lev} mb' for var in ('HGT','TMP') for lev in (300,500,700,850,925)):
  print(line,flush=True)

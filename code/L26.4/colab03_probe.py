import urllib.request
u='https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20240401/conus/hrrr.t00z.wrfsfcf00.grib2.idx'
try:
 with urllib.request.urlopen(u,timeout=30) as f:
  s=f.read().decode()
  print('NOAA_IDX',len(s),flush=True)
  for line in s.splitlines():
   if any(t in line for t in (':HGT:surface:', ':LAND:surface:', ':VGTYP:surface:', ':SFCR:surface:', ':UGRD:10 m above ground:', ':VGRD:10 m above ground:', ':TMP:2 m above ground:', ':PRMSL:mean sea level:')):
    print(line[:200],flush=True)
except Exception as e:print('NOAA_ERROR',repr(e),flush=True)

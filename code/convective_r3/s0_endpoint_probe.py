import requests
for url in ['https://mesonet.agron.iastate.edu/geojson/network/IA_ASOS.geojson','https://mesonet.agron.iastate.edu/sites/networks.php?network=IA_ASOS&format=onlycomma','https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=DSM&sts=2022-05-01T00:00Z&ets=2022-05-02T00:00Z&tz=UTC&data=gust,peak_wind_gust,peak_wind_time,metar&format=onlycomma&missing=M&report_type=3,4']:
 try:
  r=requests.get(url,timeout=25);print(url,r.status_code,len(r.content),r.text[:280],flush=True)
 except Exception as e:print(type(e).__name__,str(e),flush=True)

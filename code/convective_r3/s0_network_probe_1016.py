import requests
u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
p={'network':'KS_ASOS','sts':'2022-05-11T00:00Z','ets':'2022-05-12T00:00Z','tz':'UTC','data':'gust,peak_wind_gust,peak_wind_time,metar','format':'onlycomma','missing':'M','report_type':'3,4'}
r=requests.get(u,params=p,timeout=45);print(r.status_code,len(r.content),r.url,r.text[:600]);print('lines',len(r.text.splitlines()))
import requests,json
u='https://erddap.aoml.noaa.gov/hdb/erddap/info/sfmr_2018_2022/index.json'
r=requests.get(u,timeout=30);print(r.status_code)
d=r.json();print([x for x in d['table']['rows'] if x[0] in ('SWS','FLAG','NGC','latitude','longitude')][:90])

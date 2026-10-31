import gzip,datetime,urllib.request
for sid,land in [('al022024','2024-07-08T08:40:00+00:00'),('al062024','2024-09-11T22:00:00+00:00')]:
 raw=gzip.decompress(urllib.request.urlopen('https://ftp.nhc.noaa.gov/atcf/archive/2024/b'+sid+'.dat.gz').read()).decode().splitlines()
 ts=sorted(set(a[2].strip() for line in raw if len(a:=[x.strip() for x in line.split(',')])>=20 and a[4]=='BEST' and a[11]=='34' and all(float(a[k])>0 for k in (8,9,17,19))))
 t=datetime.datetime.fromisoformat(land); print(sid,'window',t-datetime.timedelta(hours=12),t+datetime.timedelta(hours=12),'valid',ts[:3],ts[-3:])

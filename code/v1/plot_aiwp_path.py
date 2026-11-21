import gzip,json,urllib.request,importlib.util
from datetime import timedelta
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('old',p.parent/'chain_a.py');o=importlib.util.module_from_spec(s);s.loader.exec_module(o)
path=json.loads((p/'aiwp_path_metrics.json').read_text());t0=o.dt('202410090000')
best=o.parse_hurdat()['MILTON'][1]
best=[v for v in best if t0<=v['t']<=t0+timedelta(hours=24)]
raw=gzip.decompress(urllib.request.urlopen('https://ftp.nhc.noaa.gov/atcf/archive/2024/aal142024.dat.gz',timeout=40).read()).decode()
ofcl={}
for line in raw.splitlines():
 a=[x.strip() for x in line.split(',')]
 if len(a)>9 and a[2]=='2024100900' and a[4]=='OFCL':
  try:
   lead=int(a[5]);lat=o.atcf_coord(a[6]);lon=o.atcf_coord(a[7])
   if 0<=lead<=24:ofcl[lead]=(lat,lon)
  except ValueError:pass
print('OFCL',ofcl,'BEST',[(str(v['t']),v['lat'],v['lon']) for v in best])
fig,ax=plt.subplots(figsize=(7.5,6))
ax.plot([v['lon'] for v in best],[v['lat'] for v in best],'-ko',ms=4,label='NHC BEST (HURDAT2)')
lead=sorted(ofcl);ax.plot([ofcl[k][1] for k in lead],[ofcl[k][0] for k in lead],'-o',c='#c4493d',ms=4,label='NHC OFCL init 10-09 00Z')
pts=path['points'];ax.plot([x['lon'] for x in pts],[x['lat'] for x in pts],'-s',c='#1769aa',ms=5,label='FOUR v200 MSLP pilot')
for x in pts:ax.annotate(str(x['lead_h'])+'h',(x['lon'],x['lat']),xytext=(4,-9),textcoords='offset points',fontsize=8)
ax.grid(alpha=.3);ax.set_xlabel('Longitude °');ax.set_ylabel('Latitude °');ax.legend();ax.set_title('Milton 2024: one initialized AIWP center trace (exploratory)')
fig.text(.02,.015,'Sources: NOAA/NHC HURDAT2 & ATCF a-deck; CIRA/NOAA AIWP FOUR v200 GFS, 2024-10-09 00Z.',fontsize=7.5)
fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(p/'aiwp_milton_path_pilot.png',dpi=150);plt.close(fig)
(p/'aiwp_path_comparison.json').write_text(json.dumps({'aiwp':pts,'ofcl':ofcl,'best':[{'time':str(x['t']),'lat':x['lat'],'lon':x['lon']} for x in best]},indent=2))

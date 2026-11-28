#!/usr/bin/env python3
"""Bounded DAP ASCII checks supplementing immutable v2 inventory; no whole GRIB."""
import concurrent.futures, datetime as dt, json, pathlib, re, urllib.parse, urllib.request, urllib.error
B=pathlib.Path(__file__).resolve().parent
v=json.loads((B/'INPUT_PRECHECK_2024_v2.json').read_text())
out=B/'INPUT_PRECHECK_2024_v2_RECHECK.json'
assert not out.exists()
base='https://thredds.rda.ucar.edu/thredds/dodsC/files/g/'
def u(c,d='d084001',lead=0):
 t=dt.datetime.fromisoformat(c); stem='gfs.0p25'+('b' if d=='d084003' else '')
 return f'{base}{d}/{t:%Y}/{t:%Y%m%d}/{stem}.{t:%Y%m%d%H}.f{lead:03d}.grib2'
def fetch(url):
 try:
  with urllib.request.urlopen(url,timeout=35) as r:return {'http':r.status,'url':url,'text':r.read(150000).decode('utf-8','replace')}
 except Exception as e:return {'http':getattr(e,'code',None),'url':url,'error':str(e)}
def ascii(base_url,query):return fetch(base_url+'.ascii?'+urllib.parse.quote(query,safe=''))
def values(t):
 if not t:return []
 s=t.split('---------------------------------------------')[-1]
 return [float(x) for x in re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?',s)]
def samples(c,d,var,pressures):
 url=u(c,d);coord='isobaric1' if d=='d084003' else 'isobaric'
 cr=ascii(url,coord);levs=[int(x) for x in values(cr.get('text')) if 100<=x<=110000]
 result={'coordinate_http':cr['http'],'coordinate_url':cr['url'],'coordinate_levels_pa':levs,'samples':{}}
 for pa in pressures:
  if pa not in levs:result['samples'][str(pa)]={'status':'level_absent'};continue
  idx=levs.index(pa);r=ascii(url,f'{var}[0:1:0][{idx}:1:{idx}][300:1:300][1000:1:1000]')
  text=r.get('text','');match=re.search(r'^\[0\]\[0\]\[0\],\s*([^\s]+)',text,re.M)
  result['samples'][str(pa)]={'http':r['http'],'url':r['url'],'value':float(match.group(1)) if match and match.group(1).lower() not in ('nan','-nan') else None,'reported_pressure_pa':float(re.search(re.escape(coord)+r'\[1\]\s*\n([^\s]+)',text).group(1)) if re.search(re.escape(coord)+r'\[1\]\s*\n([^\s]+)',text) else None,'error':r.get('error')}
 return result
r=next(x for x in v['events']['E2']['24h'] if x['role']=='analysis_t0' and x['dataset']=='d084001')
c=r['cycle_utc'];report={'method':'URL-encoded DAP ASCII subsetting corrects v2 unescaped-bracket 400; no entire GRIB','q_rh':{},'middle':{},'surface':{},'apcp_bounds':{},'boundary_retry':{}}
for var in ('Specific_humidity_isobaric','Relative_humidity_isobaric'):
 report['q_rh'][var]=samples(c,'d084001',var,[85000,50000,10000,1000])
for var in ('Relative_humidity_isobaric','Temperature_isobaric'):
 report['middle'][var]=samples(c,'d084003',var,[12500,17500,22500,77500,82500,87500])
for ev,ls in v['events'].items():
 for lead,rows in ls.items():
  r=next(x for x in rows if x['role']=='analysis_t0' and x['dataset']=='d084001')
  url=u(r['cycle_utc']);key=f'{ev}_{lead}'
  report['surface'][key]={}
  for coord in ('height_above_ground2','height_above_ground3'):
   a=ascii(url,coord);report['surface'][key][coord]={'http':a['http'],'values':values(a.get('text'))[1:] if a.get('text') else [],'url':a['url'],'error':a.get('error')}
  for x in rows:
   if x['role'].startswith('apcp'):
    found=list(x.get('apcp_bounds',{}).values())
    report['apcp_bounds'][f'{key}_{x["role"]}']={'name':x.get('apcp_names_v2'),'bounds_raw':found,'confirmed_0_6h':any(y.get('values',[])[-2:]==[0.,6.] for y in found)}
for e,l,c,lead in [('E2','72h','2024-05-16T18:00:00',78),('R1','48h','2024-07-30T00:00:00',48)]:
 url=u(c,lead=lead);key=f'{e}_{l}_f{lead:03d}'
 # DDS timeout fallback to small ASCII coordinate and one first-level value, never mark full layer verified from this alone.
 a=ascii(url,'isobaric');report['boundary_retry'][key]={'coordinate_http':a['http'],'coordinate_levels_pa':[int(x) for x in values(a.get('text')) if 100<=x<=110000],'url':a['url'],'error':a.get('error')}
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('RECHECK_DONE',out,flush=True)

import pathlib,csv,json,hashlib,collections,datetime as dt,requests,io,statistics
R=pathlib.Path('/content/l2628d1');O=R/'d2';O.mkdir(exist_ok=True)
intensity=json.loads((R/'d1/metrics.json').read_text()); bystorm=collections.defaultdict(set)
for x in intensity['source']['csv_manifest']:
 name=pathlib.Path(x['file']).name; storm=name.split('_202')[0].replace('_','-').upper();issue=dt.datetime.strptime('20'+name.split('_20')[1][:8],'%Y%m%d%H');bystorm[storm].add(issue)
profile=[]
for p in sorted((R/'selected').rglob('*.csv')):
 if '/structure/data_day/' not in str(p):continue
 parts=p.parts; day=next(x for x in parts if x in ('1d','2d','3d'));storm=p.parent.name.rsplit('_',1)[0].replace('_','-');kind=p.name.split('_')[0]
 rr=list(csv.DictReader(p.open())); assert len(rr)>1 and set(rr[0])=={'radius_km','mean_wind_speed_ms'}
 best=max(rr,key=lambda r:float(r['mean_wind_speed_ms']))
 profile.append({'storm':storm,'day':day,'variable':'azimuthal-mean wind speed','kind':kind,'n_radius':len(rr),'radius_min_km':float(rr[0]['radius_km']),'radius_max_km':float(rr[-1]['radius_km']),'radial_step_first_km':float(rr[1]['radius_km'])-float(rr[0]['radius_km']),'profile_peak_radius_km':float(best['radius_km']),'profile_peak_wind_ms':float(best['mean_wind_speed_ms']),'source_path':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'time_utc':None,'center':None,'geolocation':None})
assert len(profile)==90
# Candidate match is an upper bound only: files have no issue or valid timestamp. Match every issue+nominal 24/48/72 h.
sids={'NANMADOL':'wp162022','GUCHOL':'wp032023','KHANUN':'wp062023','SAOLA':'wp092023','HAIKUI':'wp102023','MARIA':'wp052024','SHANSHAN':'wp102024','BEBINCA':'wp142024','MAN-YI':'wp242024','USAGI':'wp252024'}
# Use D0-supplied verified sid values instead of assuming enumeration.
src=json.loads(pathlib.Path('/content/l2628d1/d0_sources.json').read_text()) if pathlib.Path('/content/l2628d1/d0_sources.json').exists() else None
if src:
 sids={k:next(iter(v['sids'].values()))['usa_atcf_id'][-1].strip().lower() for k,v in src['ibtracs'].items()}
scenes=[];errors=[]
for storm,sid in sorted(sids.items()):
 try:
  r=requests.get('https://cyclobs.ifremer.fr/app/api/getData',params={'sid':sid,'include_cols':'all','product_type':'gridded'},timeout=50);r.raise_for_status()
  unique={x['data_url']:x for x in csv.DictReader(io.StringIO(r.text)) if x.get('data_url')}
  for url,x in unique.items():
   if x.get('eye_in_acq','').strip().lower()!='true':continue
   t=dt.datetime.fromisoformat(x['acquisition_start_time']);candidate=[]
   for day in (1,2,3):
    for issue in bystorm[storm]:
     target=issue+dt.timedelta(days=day);gap=abs((t-target).total_seconds())/3600
     if gap<=3:candidate.append({'day':day,'issue':issue.isoformat(),'nominal_time':target.isoformat(),'offset_h':round(gap,4)})
   if candidate:scenes.append({'storm':storm,'sid':sid,'acquisition':t.isoformat(),'eye_center':x.get('eye_center'),'center_quality':x.get('analysis_center_quality_flag'),'url_sha256':hashlib.sha256(url.encode()).hexdigest(),'candidate_matches':candidate})
  print('SAR',storm,sid,len(unique),flush=True)
 except Exception as e:errors.append({'storm':storm,'sid':sid,'error':repr(e)});print('SAR_ERROR',storm,str(e),flush=True)
out={'source_archive_sha256':intensity['source']['zenodo_zip_sha256'],'profile_files':profile,'profile_file_count':len(profile),'nominal_scene_candidates':scenes,'nominal_unique_scene_count':len(scenes),'nominal_unique_storm_count':len(set(s['storm'] for s in scenes)),'api_errors':errors,'qualified_scene_count':0,'qualified_scene_count_note':'no released structure profile has valid UTC or issue time, geographic grid or center; no verifiable scene-to-structure-field alignment; 0 qualified, not 0 available SAR scenes','model_to_sar_rmw_median_relative_error':{'sr':None,'interpolated':None,'pangu':None},'scatterometer_r17':None,'scatterometer_reason':'Only anonymous catalog/product metadata verified; OSI SAF historical Data Store downloads require token, FTP credentials. More fundamentally author 1d/2d/3d radial-mean profiles have no geolocation, issue/valid time or 2D wind grid, thus quadrant R17 and >=2RMW azimuthal comparison are uncomputable even with scatterometer.'}
(O/'structure_audit.json').write_text(json.dumps(out,indent=2));print('STRUCT_DONE',len(profile),len(scenes),len(set(s['storm'] for s in scenes)),len(errors),flush=True)

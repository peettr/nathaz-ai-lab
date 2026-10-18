"""Resume eight failed Q5 seasons without modifying the 28 completed Colab rows."""
from pathlib import Path
import json,shutil,subprocess,sys,datetime
src=Path('/content/sens2');rt=Path('/content/sens_retry');dst=Path('/content/sens4')
rt.mkdir(exist_ok=False)
for name in ('source_stage.tar','final2_qc.json','tacc_raw_receipts.jsonl','static_gates.csv','station_admission.csv','era_seasons.jsonl','fallback_isd.json','isd_station_ids.json'):
 shutil.copyfile(src/name,rt/name)
errors=[json.loads(x) for x in (src/'qc_station_seasons.jsonl').read_text().splitlines() if '"error"' in x]
assert len(errors)==8,errors
(rt/'selected_keys.json').write_text(json.dumps([[x['station'],x['season_year']] for x in errors]))
s=(src/'cached_source.py').read_text();old="  if name in ISD_INDEX:return ISD_INDEX[name]\n"
assert s.count(old)==1
s=s.replace(old,"  if name in ISD_INDEX:return ISD_INDEX[name]\n  fallback=json.loads((root/'fallback_isd.json').read_text())\n  if url in fallback:return fallback[url].encode()\n")
(rt/'cached_source.py').write_text(s)
s=(src/'qc_noq3_colab.py').read_text();assert s.count('/content/sens2')==2
(rt/'qc_retry.py').write_text(s.replace('/content/sens2','/content/sens_retry'))
# Outputs are exclusively new; prior 28 successful rows and eight error records untouched.
s='''import sys,subprocess,pathlib,json,datetime,traceback,csv
src=pathlib.Path('/content/sens2');r=pathlib.Path('/content/sens_retry');d=pathlib.Path('/content/sens4')
try:
 z=subprocess.run([sys.executable,str(r/'qc_retry.py')],cwd='/content',check=True)
 done=json.loads((r/'qc.done').read_text());assert done['rows']==8 and done['errors']==0,done
 print('RETRY_QC_DONE',done,flush=True)
 d.mkdir(exist_ok=False)
 import shutil
 for name in ('static_gates.csv','station_admission.csv','era_seasons.jsonl'):shutil.copyfile(src/name,d/name)
 original=json.loads((src/'final2_qc.json').read_text()); a={(x['station'],x['season_year']):x for x in original.values()};assert len(a)==435
 good=[json.loads(x) for x in (src/'qc_station_seasons.jsonl').read_text().splitlines() if '"error"' not in x]
 retry=[json.loads(x) for x in (r/'qc_station_seasons.jsonl').read_text().splitlines()];assert len(good)==28 and len(retry)==8
 b={(x['station'],x['season_year']):x for x in good+retry};assert len(b)==36 and set(b)<=set(a)
 changed=[]
 for k,new in b.items():
  old=a[k];v=lambda x:(x['qc_peak']['kn'],x['qc_peak']['event_utc']) if x.get('qc_peak') else None
  if v(old)!=v(new) or old['valid']!=new['valid']:
   changed.append({'station':k[0],'season_year':k[1],'before':v(old),'after':v(new),'valid_before':old['valid'],'valid_after':new['valid']})
  a[k]=new
 with (d/'qc_station_seasons.jsonl').open('x') as f:
  for x in a.values():f.write(json.dumps(x,ensure_ascii=False)+'\\n')
 (d/'changed_seasons.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2))
 (d/'merge_provenance.json').write_text(json.dumps({'final2':435,'first_success':28,'retry_success':8,'changed':len(changed),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 print('MERGED',len(a),len(b),len(changed),flush=True)
 for name in ('score_sens_colab_final.py','gev_sens_colab_final.py','derive_colab.py'):
  subprocess.run([sys.executable,str(src/name)],cwd='/content',check=True)
  print('STEP_DONE',name,flush=True)
 assert all((d/x).exists() for x in ('decision.json','gev_counts.json','x10_changes.csv'))
 (r/'pipeline.exit.json').write_text(json.dumps({'returncode':0,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
except Exception as ex:
 traceback.print_exc()
 (r/'pipeline.exit.json').write_text(json.dumps({'returncode':1,'error':repr(ex),'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}));sys.exit(1)
'''
(rt/'pipeline.py').write_text(s)
with (rt/'pipeline.log').open('x') as log:
 proc=subprocess.Popen([sys.executable,str(rt/'pipeline.py')],cwd='/content',stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(rt/'pid.json').write_text(json.dumps({'pid':proc.pid}))
print('RETRY_STARTED',proc.pid)

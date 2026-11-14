from pathlib import Path
import json,shutil
src=Path('/content/sens2'); dst=Path('/content/sens4');dst.mkdir(exist_ok=False)
for f in ('static_gates.csv','station_admission.csv','era_seasons.jsonl'):shutil.copyfile(src/f,dst/f)
a={ (r['station'],r['season_year']):r for r in json.loads((src/'final2_qc.json').read_text()).values() }
b={ (r['station'],r['season_year']):r for r in map(json.loads,(src/'qc_station_seasons.jsonl').read_text().splitlines()) }
assert len(a)==435 and len(b)==36 and set(b)<=set(a)
changed=[]
for k,z in b.items():
 old=a[k]; v=lambda x:(x['qc_peak']['kn'],x['qc_peak']['event_utc']) if x.get('qc_peak') else None
 if v(old)!=v(z) or old['valid']!=z['valid']:
  changed.append({'station':k[0],'season_year':k[1],'before':v(old),'after':v(z),'valid_before':old['valid'],'valid_after':z['valid']})
 a[k]=z
with (dst/'qc_station_seasons.jsonl').open('x') as f:
 for z in a.values():f.write(json.dumps(z,ensure_ascii=False)+'\n')
(dst/'changed_seasons.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2))
print('MERGE',len(a),len(b),len(changed),changed,flush=True)

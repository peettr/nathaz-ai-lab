from pathlib import Path
import tarfile,json,hashlib
p=Path('/content/sens2');r=Path('/content/sens_retry');d=Path('/content/sens4')
assert json.loads((r/'analysis.done.json').read_text())['n_gev']==29
files={'decision.json':d/'decision.json','station_params.csv':d/'station_params.csv','loso_results.csv':d/'loso_results.csv','qc_station_seasons.jsonl':d/'qc_station_seasons.jsonl','changed_seasons.json':d/'changed_seasons.json','x10_changes.csv':d/'x10_changes.csv','gev_lmom_sensitivity.csv':d/'gev_lmom_sensitivity.csv','gev_with_baseline.csv':d/'gev_with_baseline.csv','gev_counts.json':d/'gev_counts.json','merge_provenance.json':d/'merge_provenance.json','fallback_provenance.json':p/'fallback_provenance.json','qc_first.done':p/'qc.done','qc_retry.done':r/'qc.done','qc_first.log':p/'qc_log.csv','qc_retry.log':r/'qc_log.csv','analysis.done.json':r/'analysis.done.json','retry_pipeline.log':r/'pipeline.log'}
assert all(f.exists() for f in files.values())
with tarfile.open('/content/noq3_results.tar','w') as t:
 for name,f in files.items():t.add(f,arcname=name)
print('RESULTS',len(files),Path('/content/noq3_results.tar').stat().st_size,'SHA256',hashlib.sha256(Path('/content/noq3_results.tar').read_bytes()).hexdigest())

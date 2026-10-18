import pathlib,subprocess,datetime
r=pathlib.Path('/content');print('UTC',datetime.datetime.now(datetime.timezone.utc),flush=True)
for f in ['s1_corrected_ab.log','s1_ab_corrected_rows.jsonl','s1_ab_corrected_metrics.json','s1_c_corrected.log','s1_c_corrected_metrics.json']:
 p=r/f;print(f,'EXISTS',p.exists(),'SIZE',p.stat().st_size if p.exists() else 0,flush=True)
 if p.exists() and f.endswith('.log'):print(p.read_text(errors='replace')[-2500:],flush=True)
print(subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout[-3000:],flush=True)

import pathlib,subprocess,json,datetime
r=pathlib.Path('/content');p=r/'s1_ab_full_rows.jsonl'
print('UTC',datetime.datetime.now(datetime.timezone.utc).isoformat(),'ROWS',len(p.read_text().splitlines()) if p.exists() else 0,'METRICS',(r/'s1_ab_full_metrics.json').exists())
q=subprocess.run(['pgrep','-af','s1_ab_full_1016.py'],capture_output=True,text=True);print('PROC',q.stdout[:400])
log=r/'s1_ab_full_v2.log';print('TAIL','\n'.join(log.read_text(errors='replace').splitlines()[-7:]) if log.exists() else 'NONE')

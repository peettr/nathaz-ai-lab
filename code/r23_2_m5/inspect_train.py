from pathlib import Path
import json, datetime
p=Path('/content/m5'); d=p/'train_gfs'
expected=[(datetime.datetime(2023,9,29,tzinfo=datetime.timezone.utc)+datetime.timedelta(hours=6*i)).strftime('%Y%m%d%H') for i in range(376)]
missing=[x for x in expected if not (d/(x+'.csv')).exists()]
print(json.dumps({'exists':p.exists(),'gfs_count':len(list(d.glob('*.csv'))),'missing':missing,'total_bytes':sum(x.stat().st_size for x in d.glob('*.csv')),'obs_count':len(list((p/'obs').glob('obs_*.csv'))),'files':[(str(x),x.stat().st_size) for x in p.iterdir() if x.is_file()],'error_tail':(p/'errors.jsonl').read_text()[-3000:] if (p/'errors.jsonl').exists() else None,'log_tail':(p/'train_gfs.log').read_text()[-1000:] if (p/'train_gfs.log').exists() else None},default=str))

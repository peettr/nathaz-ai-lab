from pathlib import Path
p=Path('/content/site_stage_v2');f=p/'minute_sensitivity.jsonl';log=p/'minute.log'
print('minute seasons',sum(1 for _ in f.open()) if f.exists() else 0,'done',p.joinpath('minute.done').exists());print('tail',log.read_text(errors='replace')[-1000:] if log.exists() else '')

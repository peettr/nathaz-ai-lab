from pathlib import Path
p=Path('/content/site_stage_v2');f=p/'era_seasons.jsonl';log=p/'era.log'
print('era seasons',sum(1 for _ in f.open()) if f.exists() else 0,'done',p.joinpath('era.done').exists());print('tail',log.read_text(errors='replace')[-1500:] if log.exists() else '')

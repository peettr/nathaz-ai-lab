from pathlib import Path
import os,json
p=Path('/content/site_stage_v2');f=p/'station_only_seasons.jsonl';log=p/'admission.log'
print('rows',sum(1 for _ in f.open()) if f.exists() else 0,'pid',p.joinpath('admission.pid').read_text() if p.joinpath('admission.pid').exists() else '', 'alive',Path('/proc/'+p.joinpath('admission.pid').read_text()).exists() if p.joinpath('admission.pid').exists() else False)
print('tail',log.read_text(errors='replace')[-1400:] if log.exists() else '')

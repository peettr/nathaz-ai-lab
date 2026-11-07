from pathlib import Path
p=Path('/content/l264a100/texas/west_batch_v3.log');s=p.read_text(errors='replace');print(s[:4000]);print('TAIL',s[-2200:])

from pathlib import Path
p=Path('06_Logs/L26.13/v2')
s=(p/'finish_v2b.py').read_text().replace("(P/'finish2.json').write_text", "(P/'finish3.json').write_text").replace("(P/'finish2.done').write_text", "(P/'finish3.done').write_text")
(p/'finish_v2c.py').write_text(s)
q=(p/'launch_finish2.py').read_text().replace('finish2.log','finish3.log').replace('finish_v2b.py','finish_v2c.py')
(p/'launch_finish3.py').write_text(q)

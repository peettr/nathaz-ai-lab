#!/usr/bin/env python3
"""Read-only aggregate for the completed A1 run; emit JSON on stdout."""
import csv
import hashlib
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path

root = Path.home() / 'ftkb_figures/full_v2'
conn = sqlite3.connect(f'file:{root / "figures_full.sqlite"}?mode=ro', uri=True)
result = {'schema': {table: conn.execute(f'PRAGMA table_info({table})').fetchall() for table in ('documents', 'figures')},
          'integrity': conn.execute('PRAGMA integrity_check').fetchone()[0],
          'documents': conn.execute('SELECT source_library,status,count(*),sum(figures),sum(captioned) FROM documents GROUP BY source_library,status ORDER BY source_library,status').fetchall(),
          'figures': conn.execute('SELECT source_library,kind,count(*),sum(caption_text IS NOT NULL) FROM figures GROUP BY source_library,kind ORDER BY source_library,kind').fetchall()}
conn.close()
compact = sqlite3.connect(f'file:{root / "figures_compact.sqlite"}?mode=ro', uri=True)
result['compact_integrity'] = compact.execute('PRAGMA integrity_check').fetchone()[0]
result['compact_counts'] = compact.execute('SELECT source_library,count(*) FROM figures GROUP BY source_library ORDER BY source_library').fetchall()
compact.close()
with (root/'pairs_50.csv').open(newline='') as fh:
    rows=list(csv.DictReader(fh))
result['pairs']={'rows':len(rows),'kinds':dict(Counter(row['kind'] for row in rows)),
                 'cards':len(list((root/'pairs_50').glob('*.jpg')))}
result['files']={}
for name in ('figures_full.sqlite','figures_compact.sqlite','vectors_full_v2.npy','vectors_full_v2.json','pairs_50.csv'):
    path=root/name
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda:fh.read(4*1024*1024),b''):h.update(chunk)
    result['files'][name]={'bytes':path.stat().st_size,'sha256':h.hexdigest()}
result['thumbs']={'bytes':0,'files':0}
for dirpath,dirs,files in os.walk(root/'thumbs'):
    for name in files:
        p=Path(dirpath)/name
        result['thumbs']['files']+=1
        result['thumbs']['bytes']+=p.stat().st_size
result['root_entries']=sorted(p.name for p in root.iterdir())
print(json.dumps(result,ensure_ascii=False))

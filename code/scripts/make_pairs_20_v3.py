#!/usr/bin/env python3
"""Fixed-seed 20 review pairs from freshly re-rendered fallback figures."""
import argparse,csv,random,sqlite3,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--台式机',required=True);p.add_argument('--endnote-db',required=True);p.add_argument('--zotero-db',required=True);p.add_argument('--root',required=True);p.add_argument('--seed',type=int,default=20261017);a=p.parse_args()
root=Path(a.root);out=root/'pairs_20_v3';csvfile=root/'pairs_20_v3_cards.csv'
if out.exists() or csvfile.exists():raise FileExistsError('refusing overwrite existing v3 pairs')
rows=[]
for db in [a.desktop_db,a.endnote_db,a.zotero_db]:
    c=sqlite3.connect('file:'+db+'?mode=ro',uri=True)
    rows.extend(c.execute("SELECT fig_id,source_library,physical_page,caption_text,thumb_path,kind FROM figures WHERE caption_text IS NOT NULL AND kind IN ('page_region','vector') AND extractor_version='a1-pilot-4' AND caption_text NOT GLOB '表*' AND caption_text NOT LIKE 'Table %' ORDER BY fig_id"));c.close()
rows.sort(key=lambda x:x[0]);picked=random.Random(a.seed).sample(rows,20)
with csvfile.open('x',newline='') as f:
    w=csv.writer(f);w.writerow(('fig_id','source_library','physical_page','caption_text','thumb_path','kind'));w.writerows(picked)
subprocess.run([str(Path.home()/'ftkb_figures/venv/bin/python'),str(Path.home()/'ftkb_figures/scripts_restart_20261016/make_pairs_v2.py'),'--csv',str(csvfile),'--thumbs',str(root/'thumbs'),'--out',str(out)],check=True)
print('eligible',len(rows),'picked',len(picked),'libraries',sorted(set(x[1] for x in picked)))

#!/usr/bin/env python3
"""Produce a new table-free int8 vector index by selecting precomputed rows."""
import argparse,json,sqlite3
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args()
if Path(a.out+'.npy').exists() or Path(a.out+'.json').exists():raise FileExistsError('refusing overwrite')
ids=json.load(open(a.source+'.json'));v=np.load(a.source+'.npy',mmap_mode='r');lookup={fid:i for i,fid in enumerate(ids)}
c=sqlite3.connect('file:'+a.db+'?mode=ro',uri=True)
keep=[r[0] for r in c.execute("SELECT fig_id FROM figures WHERE caption_text IS NOT NULL AND kind!='table' ORDER BY fig_id")];c.close()
if not all(x in lookup for x in keep):raise ValueError('missing encoded figure')
np.save(a.out+'.npy',np.asarray(v[[lookup[x] for x in keep]]));Path(a.out+'.json').write_text(json.dumps(keep))
print('selected',len(keep),'of',len(ids))

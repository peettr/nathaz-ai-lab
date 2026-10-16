#!/usr/bin/env python3
"""Symmetric post-freeze exclusions, preserving original per-question rows."""
import csv
from pathlib import Path
R=Path(__file__).resolve().parent.parent
bad={'R17','R24','R30'}
a=list(csv.DictReader((R/'retrieval_round2_rows.csv').open()))
fields=['group','stratum','method','N_raw','N_adjudicated','page_hits5_raw','page_hits5_adjudicated','doc_hits5_raw','doc_hits5_adjudicated','invalid_excluded']
with (R/'retrieval_round2_adjudicated.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fields);w.writeheader()
 for group,stratum,method in sorted({(x['group'],x['stratum'],x['method']) for x in a}):
  raw=[x for x in a if (x['group'],x['stratum'],x['method'])==(group,stratum,method)]
  ok=[x for x in raw if not(group=='round2' and x['id'] in bad)]
  w.writerow(dict(group=group,stratum=stratum,method=method,N_raw=len(raw),N_adjudicated=len(ok),page_hits5_raw=sum(int(x['page_hit5']) for x in raw if x['page_hit5']!=''),page_hits5_adjudicated=sum(int(x['page_hit5']) for x in ok if x['page_hit5']!=''),doc_hits5_raw=sum(int(x['doc_hit5']) for x in raw),doc_hits5_adjudicated=sum(int(x['doc_hit5']) for x in ok),invalid_excluded=','.join(sorted(set(x['id'] for x in raw)-set(x['id'] for x in ok)))))
print('wrote',R/'retrieval_round2_adjudicated.csv')

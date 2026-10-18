#!/usr/bin/env python3
"""Read-only dual-library retrieval CLI, unique normalized title + physical page."""
import argparse,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import search as bm25
from bilingual import search as chinese

def unique(rows,n):
 out=[];seen=set()
 for x in rows:
  ident=(re.sub(r'[^a-z0-9\u3400-\u9fff]','',x['title'].casefold()),x['page'])
  if ident in seen:continue
  seen.add(ident);out.append(x)
  if len(out)>=n:break
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('-n',type=int,default=5);p.add_argument('--bm25',action='store_true');a=p.parse_args()
 for x in unique((bm25 if a.bm25 else chinese)(a.query,max(100,a.n*20)),a.n):
  lib='EndNote' if x['key'].startswith('END-') else 'Zotero'
  print(f"{x['title']} ({x['year'] or 'unknown year'}) {lib} key={x['key']} PDF physical p.{x['page']}\n  {x['text'][:300]}\n")

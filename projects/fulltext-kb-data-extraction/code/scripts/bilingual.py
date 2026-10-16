#!/usr/bin/env python3
"""CPU-only hybrid lexical search: CJK trigram + English FTS5 BM25; no external calls."""
import argparse,re,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import DB,search as english_search
CDB=Path('./ftkb/cjk.sqlite')
# Fixed domain glossary, written before supplementary scoring. This is not general translation.
GLOSS={'下击暴流':'downburst','微下击暴流':'microburst','风速':'wind speed','风场':'wind field','风压':'wind pressure','高层':'high rise','风谱':'wind spectrum','功率谱':'power spectrum','结构响应':'structural response','风洞':'wind tunnel','计算流体力学':'computational fluid dynamics','湍流':'turbulence','地表层':'surface layer','边界层':'boundary layer','余谱':'cospectrum','静力学':'hydrostatic','气压':'pressure','重力':'gravity','方程':'equation','气象学':'meteorology','圆柱':'cylinder','涡脱落':'vortex shedding','无量纲':'dimensionless','频率':'frequency','直径':'diameter','时间步':'time step','稳定性':'stability','库朗':'Courant','有限差分':'finite difference','湍流通量':'turbulent flux','大气':'atmospheric','均匀':'uniform','最大风速':'maximum wind speed','水平尺度':'horizontal scale','生命周期':'lifetime','工程':'engineering','强对流':'severe convective','建筑':'building','尾流':'wake','动力':'dynamics','归一化':'normalization'}
def build():
 a=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
 b=sqlite3.connect(CDB)
 b.execute('CREATE VIRTUAL TABLE IF NOT EXISTS cjk USING fts5(title,text,tokenize="trigram")')
 b.execute('CREATE TABLE IF NOT EXISTS done(id INTEGER PRIMARY KEY)')
 n=0
 for id,title,text in a.execute('SELECT id,title,text FROM pages WHERE title GLOB "*[一-龥]*" OR text GLOB "*[一-龥]*"'):
  if b.execute('SELECT 1 FROM done WHERE id=?',(id,)).fetchone():continue
  b.execute('INSERT INTO cjk(rowid,title,text) VALUES(?,?,?)',(id,title,text))
  b.execute('INSERT INTO done(id) VALUES(?)',(id,));n+=1
  if n%1000==0:b.commit();print('cjk',n,flush=True)
 b.commit();print('CJK index pages',b.execute('SELECT COUNT(*) FROM done').fetchone()[0],'new',n,flush=True)
def search(query,n=5):
 original=english_search(query,100)
 translates=[v for k,v in GLOSS.items() if k in query]
 # Reduce overly generic expansions without privileging benchmark questions.
 translates=list(dict.fromkeys(translates))
 expanded=english_search(' '.join(translates),100) if translates else []
 cn=re.findall(r'[\u3400-\u9fff]{3,}',query)
 cjk=[]
 if cn and CDB.exists():
  b=sqlite3.connect(f'file:{CDB}?mode=ro',uri=True)
  a=sqlite3.connect(f'file:{DB}?mode=ro',uri=True);a.row_factory=sqlite3.Row
  # Character trigrams tolerate paraphrases and absent word boundaries.
  grams=list(dict.fromkeys(s[i:i+3] for s in cn for i in range(len(s)-2)))
  expr=' OR '.join('"'+v+'"' for v in grams[:80])
  try:
   ids=[row[0] for row in b.execute('SELECT rowid FROM cjk WHERE cjk MATCH ? ORDER BY bm25(cjk) LIMIT 100',(expr,))]
   cjk=[dict(a.execute('SELECT * FROM pages WHERE id=?',(i,)).fetchone()) for i in ids]
  except sqlite3.Error as e:print('CJK warning',e,file=sys.stderr)
 scores={};rows={}
 for group,weight in [(original,1),(expanded,0.7),(cjk,1.2)]:
  for pos,row in enumerate(group):
   k=row['id'];scores[k]=scores.get(k,0)+weight/(30+pos+1);rows[k]=row
 return [dict(rows[k],score=scores[k]) for k in sorted(scores,key=scores.get,reverse=True)[:n]]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('cmd',choices=['build','search']);p.add_argument('query',nargs='?');p.add_argument('-n',type=int,default=5);x=p.parse_args()
 if x.cmd=='build':build()
 else:
  for r in search(x.query,x.n):print(f"{r['title']} ({r['year']}) key={r['key']} PDF p.{r['page']} [{r['score']:.4f}]\n  {r['text'][:260]}\n")

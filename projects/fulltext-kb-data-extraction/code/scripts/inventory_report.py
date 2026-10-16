#!/usr/bin/env python3
"""Post-index conservative inventory. Never alters original manifests or source libraries."""
import csv,json,re,sqlite3,collections
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
I=Path('./ftkb/index.sqlite')
def main():
 a=list(csv.DictReader((R/'corpus_manifest.csv').open()))
 c=sqlite3.connect(f'file:{I}?mode=ro',uri=True)
 statuses=dict(c.execute('select attachment,status from processed'))
 pages=dict(c.execute('select attachment,count(*) from pages group by attachment'))
 chars={}
 for k,t in c.execute('select attachment,group_concat(substr(text,1,1200)," ") from pages where page<=5 group by attachment'):
  text=t or '';chars[k]=(len(re.findall('[\u3400-\u9fff]',text)),len(re.findall('[A-Za-z]',text)))
 # DOI and title clustering: each connected component is one putative work.
 parent=list(range(len(a)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 keys={}
 for i,x in enumerate(a):
  title=x['identity'] if x['identity'].startswith('title:') else ''
  # The initial manifest used DOI over title; recover title from title column to match EndNote filenames.
  import unicodedata
  norm=''.join(y for y in unicodedata.normalize('NFKC',x['title']).casefold() if y.isalnum())
  aliases=([('doi',x['doi'])] if x['doi'].startswith('10.') else [])+([('title',norm)] if len(norm)>=20 else [])
  for alias in aliases:
   if alias in keys:parent[root(i)]=root(keys[alias])
   else:keys[alias]=i
 clusters=collections.defaultdict(list)
 for i,x in enumerate(a):clusters[root(i)].append(i)
 # Ambiguous title collisions could be distinct editions; count is approximate.
 overlaps=sum(len({a[i]['source'] for i in indices})>1 for indices in clusters.values())
 lines=['# Zotero + EndNote PDF 语料盘点（10-13，美东）','',
 '源库只读；Zotero 元数据取 WSL 本地复制库，EndNote .enl 未解析：以文件名派生标题，故 DOI 仅 Zotero 有，EndNote 类型/年代和跨库去重是保守近似。所有篇数按实际可见 PDF 附件，不等于 Zotero itemType 总条目数。','',
 '| 来源 | PDF附件（去重前） | 与另一库合并后的独立候选篇数* | 大小 | 可抽文本附件 | 无文本附件 | 抽取失败 | 英/中/混合/未知** | book / bookSection / thesis / journalArticle / 其他或未分类 |',
 '|---|---:|---:|---:|---:|---:|---:|---|---|']
 for src in ('Zotero','EndNote'):
  subset=[x for x in a if x['source']==src]
  ok=sum(statuses.get(x['attachment'])=='ok' for x in subset)
  no=sum(statuses.get(x['attachment'])=='no_text' for x in subset)
  fail=len(subset)-ok-no
  types=collections.Counter(x['type'] for x in subset)
  lang=collections.Counter()
  for x in subset:
   h,e=chars.get(x['attachment'],(0,0))
   lang['未知' if h+e<80 else '混合' if h>=20 and e>=100 else '中' if h>=20 else '英']+=1
  unique_src=len({root(i) for i,x in enumerate(a) if x['source']==src})
  lines.append(f"| {src} | {len(subset)} | {unique_src} | {sum(int(x['size']) for x in subset)/1024**3:.2f} GiB | {ok} | {no} | {fail} | {lang['英']}/{lang['中']}/{lang['混合']}/{lang['未知']} | {types['book']}/{types['bookSection']}/{types['thesis']}/{types['journalArticle']}/{len(subset)-sum(types[k] for k in ('book','bookSection','thesis','journalArticle'))} |")
 lines+=['',f'合并候选篇数：{len(clusters)}；跨库同题名候选簇 {overlaps}；去重前附件 {len(a)}。同库重复附件、不同版本/同名碰撞不保证属于同一作品。EndNote 文件名截断、期刊与书名无法总是区分；因此不能声称精确 DOI 去重或精确书籍/论文分类。',
 '*“来源独立候选篇数”是各库内部去重；两行不可直接相加。仅相同 DOI 或规范化标题形成簇；EndNote 没有可靠 DOI，同名但差异化副标题可能漏并。',
 '**前5物理页抽样：CJK字符≥20判中，英文字母≥100且有中判混合；不足80可识别字符判未知。这不是全文语言分类。文件名含汉字也不代表全文中文。',
 f'索引非空物理页总数：{c.execute("select count(*) from pages").fetchone()[0]}。no_text 是整份 PDF 抽不到≥40字符的页，不全等于扫描件；失败/超时更不可归扫描。无文本比例约 {sum(statuses.get(x["attachment"])=="no_text" for x in a)/len(a):.1%}，为 OCR 工作量下界；真实扫描页需逐页图像检查，尚未量测，不能给可靠总工时。',
 'EndNote 书籍标记仅文件名显式提示的下界；更多书混在未分类中。由非空页数≥150 的 EndNote 文档可列为“长文档候选”，但学位论文也会混入，不用作精确书数。',
 f'EndNote 长文档候选（≥150 个可读页）：{sum(pages.get(x["attachment"],0)>=150 for x in a if x["source"]=="EndNote")}。',
 '本机索引：./ftkb/index.sqlite；仅索引有可抽文本层的 PDF 页，未做 OCR。PDF 物理页与期刊印刷页不混用。']
 (R/'corpus_inventory.md').write_text('\n'.join(lines)+'\n')
 print('\n'.join(lines))
if __name__=='__main__':main()

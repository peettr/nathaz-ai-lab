#!/usr/bin/env python3
"""Read-only aggregation of Kareem source ledgers; writes only this directory.
Stable KA ids are retained from existing output and never renumbered on rerun.
"""
import csv, json, os, re, sqlite3, collections, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]; OUT=pathlib.Path(__file__).resolve().parent
ART=pathlib.Path('./.hermes/profiles/researchos-literature/artifacts')
ZOT=pathlib.Path('./Zotero/zotero.sqlite')
def read(path):
 with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def norm(s):return re.sub(r'[^a-z0-9]+','',str(s or '').lower())
def doi(s):return re.sub(r'^https?://(?:dx\.)?doi\.org/','',str(s or '').strip().lower()).strip()
def yr(s):
 m=re.search(r'\b(?:19|20)\d{2}\b',str(s or ''));return m.group() if m else ''
def unique(s):return ';'.join(dict.fromkeys(x for x in s if x))
def item_type(s):
 s=(s or '').lower()
 if 'thesis' in s or 'dissertation' in s:return 'thesis'
 if 'chapter' in s:return 'book-chapter'
 if 'proceeding' in s or 'conference' in s:return 'conference'
 if s in ('article','review','journal-article'):return 'article'
 return '其他'
# Explicit, unchanged source topic rules, only used for missing provenance topic.
TOPICS={
'非平稳风与雷暴风':r'non[ -]?station|non[ -]?synoptic|downburst|thunderstorm|gust[ -]?front|transient wind|hurricane|typhoon|tornado|tropical cyclone|tropical storm',
'阵风因子与峰值因子':r'gust factor|peak factor|gust effect|gust response|gust.front factor|wind speed averaging|averaging interval|gust loading',
'高层建筑气动与风振':r'tall building|high[ -]?rise|building|aeroelastic|wind[ -]?excit|wind[ -]?induc|damping|slosh|tuned mass|motion|vortex|interference|buffeting',
'随机过程模拟与非高斯':r'random|stochastic|non[ -]?gaussian|non[ -]?normal|simulation|spectral|spectrum|spectra|arma|quadratic|probabilistic|coherence|correlation|turbulence',
'数据驱动与机器学习':r'machine learning|data[ -]?driven|database|digital twin|neural|knowledge[ -]?based|surrogate|deep learning|artificial intelligence',
'桥梁气动与颤振':r'bridge|flutter|cable|suspension span',
'可靠度与性能化设计':r'reliab|performance[ -]?based|risk|hazard|uncertainty|optim|design wind|codif|load combination|fragility|failure|safety',
'风浪/海洋结构':r'\bwave(?:s)?\b|ocean|offshore|marine|tension[ -]?leg|\bsurge\b|sea surface|platform|hydrodynamic',
'计算风工程与数值模型':r'computational fluid|\bcfd\b|large[ -]?eddy|numerical simulation|computational wind|wind tunnel|fluid[ -]?structure|mesoscale|microscale|numerical models|boundary layer model',
'结构控制与状态识别':r'control|absorber|damper|hybrid system|system identification|virtual dynamic shaker|morphing|actuation',
'风荷载与试验方法':r'wind load|wind force|wind engineering|dynamic load|pressure|model data|structural design|wind effects|wind[ -]?turbine|aerodynamic response',
'信号处理与数值方法':r'interpolation|time[ -]?frequency|signal analysis|discrete[ -]?time|statistical cubicization|nonlinear|predictive model',
'教学讲稿与非论文材料':r'microsoft powerpoint|presentation|intro wind|topics in the wind|living laboratory|crowdsourcing|the question describing'}
def topic(title):return ';'.join(k for k,p in TOPICS.items() if re.search(p,title or '',re.I)) or '风工程综合/其他待细分'
def add_note(row,s):
 if s and s not in row['note']:row['note']+=(('；' if row['note'] else '')+s)
def add_key(row,col,val):
 if val:row[col]=unique((row[col].split(';') if row[col] else [])+[val])
def set_path(row,p,source=''):
 if not p:return
 if re.match(r'^[a-zA-Z]:\\',p):
  row['remote_only']='是';add_key(row,'remote_pdf_path',p);add_note(row,'远端路径仅供定位，未验证可访问')
 elif os.path.isfile(p):
  if p.lower().endswith('.pdf'):
   if not row['local_pdf_path'] or not os.path.isfile(row['local_pdf_path'].split(';')[0]):row['local_pdf_path']=p
   elif p not in row['local_pdf_path'].split(';'):row['local_pdf_path']+=';'+p
   row['has_fulltext']='是'
 elif source:add_note(row,source+' 登记路径本机不存在，不写入 local_pdf_path')
def main():
 source=read(ROOT/'corpus_status_r4.csv');prov=read(ROOT/'provenance/corpus_provenance.csv');inv=read(ROOT/'inventory.csv');theses=read(ROOT/'theses/theses_in_library.csv');third=read(ROOT/'third_endnote/kareem_reconciliation.csv')
 valid={r['openalex_id']:r for r in source if r['status'] not in ('not_kareem','non_paper') and not r['duplicate_of']}
 # Provenance is the approved work set; never add excluded r4 catalogue nodes.
 rows=[];by_oa={};by_wid={};by_doi={};by_title={}
 def index(row):
  if row['openalex_id']:by_oa[row['openalex_id']]=row
  if row['work_id']:by_wid[row['work_id']]=row
  if row['doi']:by_doi.setdefault(doi(row['doi']),[]).append(row)
  if row['title']:by_title.setdefault((norm(row['title']),yr(row['year'])),[]).append(row)
 def find(oa='',wid='',d='',title='',year=''):
  if oa and oa in by_oa:return by_oa[oa]
  if wid and wid in by_wid:return by_wid[wid]
  if d:
   candidates=by_doi.get(doi(d),[])
   if len(candidates)==1:return candidates[0]
  candidates=by_title.get((norm(title),yr(year)),[]) if title and year else []
  if len(candidates)==1:return candidates[0]
  return None
 def new(p):
  row={k:'' for k in FIELDS};row.update({k:p.get(k,'') for k in ['work_id','openalex_id','title','year','venue','kareem_position','n_authors','tier','invited_review','topic']})
  row.update(type=item_type(p.get('type') or ('conference' if p.get('conference')=='是' else '')),has_fulltext=p.get('has_fulltext','否') or '否',conference=p.get('conference','否'))
  row['note']='分层依据：'+(p.get('判层依据') or '缺作者信息，层未知')
  if not row['topic']:row['topic']=topic(row['title'])
  rows.append(row);index(row);return row
 for p in prov:
  if p.get('openalex_id') and p['openalex_id'] not in valid:continue
  # Historical provenance records have unique work_id or OpenAlex ID.
  if find(p.get('openalex_id'),p.get('work_id')):continue
  row=new(p);s=valid.get(row['openalex_id'],{})
  row['doi']=s.get('doi','');row['type']=item_type(s.get('type') or p.get('type'))
  if row['doi']:by_doi.setdefault(doi(row['doi']),[]).append(row)
  row['has_fulltext']='是' if s.get('status')=='库内有全文' or p.get('has_fulltext')=='是' else '否'
  row['status_source']=s.get('status') or p.get('status','')
  row['note']+='；'+(s.get('note','') or '') if s.get('note') else ''
  add_key(row,'zotero_parent_key',s.get('zotero_parent_key',''))
  add_key(row,'zotero_pdf_key',s.get('pdf_child_key',''))
  set_path(row,s.get('pdf_path',''),'r4')
 # Input inventory also holds uncatalogued works; don't merge ambiguous near matches.
 for x in inv:
  row=find(wid=x['work_id'])
  if not row:
   row=new(dict(work_id=x['work_id'],title=x['title'],year=x['year'],venue=x['venue'],topic=x['topic'],has_fulltext=x['has_fulltext'],tier='未知',**{'判层依据':'库存仅有书目，未关联可靠作者序'}))
   if x['doi']:row['doi']=x['doi'];by_doi.setdefault(doi(x['doi']),[]).append(row)
  ids=x['library_item_ids'].split(';')
  for id_ in ids:
   id_=id_.strip()
   if re.fullmatch(r'[A-Z0-9]{8}',id_):add_key(row,'zotero_parent_key',id_)
   elif id_.startswith('DSK-'):add_key(row,'ftkb_id',id_)
   elif id_:add_key(row,'endnote_id',id_)
  if x['doi'] and not row['doi']:row['doi']=x['doi']
  if x['has_fulltext']=='是':row['has_fulltext']='是'
  if x['topic']:row['topic']=x['topic']
  if x['unpublished']=='是':add_note(row,'未公开教学材料：不作公开摘引')
  if 'Desktop' in x['libraries']:
   row['remote_only']='是';add_note(row,'台式机 I: 来源，路径未在本库存表给出，须用 ftKB ID 查')
  if x['dedup_note']:add_note(row,x['dedup_note'][:300])
 # Student theses: evidence confidence retained; non-author theses not silently attributed to Kareem.
 for t in theses:
  row=find(title=t['title'],year=t['year'])
  if not row:
   row=new(dict(title=t['title'],year=t['year'],venue=t['university'],type='thesis',tier='未知',has_fulltext=t['has_fulltext'],**{'判层依据':'学位论文原文证据单独审计，未匹配作品编号'}))
  row['type']='thesis';row['thesis_role']=t['kareem_role']+'（'+t['confidence']+'；PDF物理页 '+(t['evidence_page'] or '未核')+'）'
  add_note(row,'论文证据：'+t['confidence']+'；非 Kareem 署名的学生论文不得算 Kareem 自写')
  if t['has_fulltext']=='是':row['has_fulltext']='是'
  for key in re.findall(r'Zotero ([A-Z0-9]{8})',t['library_where']):add_key(row,'zotero_parent_key',key)
  for key in re.findall(r'inventory (KRM-\d+)',t['library_where']):
   if row['work_id']!=key:add_note(row,'库存关联 '+key+'（未自动合并）')
  if 'third EndNote' in t['library_where']:add_note(row,'第三 EndNote: '+t['library_where'].split('third EndNote ')[-1].split(';')[0])
 # Third EndNote: use confirmed reconciliation only, otherwise same DOI or exact title/year.
 for x in third:
  row=find(oa=x['openalex_id'],wid=x['work_id'],d=x['doi'],title=x['title'],year=x['year'])
  if not row:
   row=new(dict(title=x['title'],year=x['year'],venue=x['journal'],type='conference' if 'proc.' in x['journal'].lower() else 'article',tier='未知',has_fulltext='否',**{'判层依据':'第三 EndNote 作者序未经可靠结构化，未知'}))
   row['doi']=x['doi'];index(row)
  add_key(row,'endnote_id','third:'+x['record_id'])
  if x['has_file']=='是' and x['file_relpath']:
   rel=x['file_relpath'].lstrip('/\\').replace('/','\\')
   set_path(row,'I:\\Endnote\\PostDocReport\\PostDocReport.Data\\'+rel)
   add_note(row,'第三 EndNote 附件文件名匹配 '+x['match_confidence']+'；不等于本机实存全文')
  if '未对上' in x['comparison']:add_note(row,'第三库对库状态：'+x['comparison']+'；谨慎核重')
 # Re-evaluate exact duplicates caused by third records, but never fuzzy merge different DOI.
 # Batch 4/5 results: exact DOI, else exact title+year only when source row year unavailable use unique title.
 batch=[ART/'kareem_round4/kareem_127_total_results.csv',ART/'kareem_round5/kareem_r5_215_total_results_v11.csv']
 for f in batch:
  for x in read(f):
   if x['result'] not in ('imported','已入库','attached_verified'):continue
   row=find(d=x['doi'])
   if not row:
    hits=[z for z in rows if norm(z['title'])==norm(x['title'])]
    if len(hits)==1:row=hits[0]
   if row:
    add_key(row,'zotero_parent_key',x['zotero_parent_key']);add_key(row,'zotero_pdf_key',x['pdf_child_key'])
    set_path(row,x['local_pdf_path'],f.name)
    row['has_fulltext']='是'
 # Earlier local path and Zotero key from r4 generally included; look up current Zotero metadata to fill paths.
 c=sqlite3.connect('file:'+str(ZOT)+'?mode=ro&immutable=1',uri=True)
 meta={}
 sql='''select i.key, f.fieldName, v.value from items i join itemData d on d.itemID=i.itemID join fields f on f.fieldID=d.fieldID join itemDataValues v on v.valueID=d.valueID where f.fieldName in ('title','DOI','date')'''
 for k,field,val in c.execute(sql):meta.setdefault(k,{})[field]=str(val or '')
 zmdoi=collections.defaultdict(list);zmtitle=collections.defaultdict(list)
 for k,m in meta.items():
  if m.get('DOI'):zmdoi[doi(m['DOI'])].append(k)
  if m.get('title') and m.get('date'):zmtitle[(norm(m['title']),yr(m['date']))].append(k)
 att=collections.defaultdict(list)
 for parent,child,path,content in c.execute('select p.key,i.key,a.path,a.contentType from itemAttachments a join items i on a.itemID=i.itemID join items p on a.parentItemID=p.itemID where a.contentType="application/pdf"'):
  att[parent].append((child,path))
 for row in rows:
  if not row['zotero_parent_key']:
   candidates=zmdoi.get(doi(row['doi']),[]) if row['doi'] else []
   if not candidates:candidates=zmtitle.get((norm(row['title']),yr(row['year'])),[])
   if len(candidates)==1:add_key(row,'zotero_parent_key',candidates[0])
  for parent in row['zotero_parent_key'].split(';'):
   for child,path in att.get(parent,[]):
    add_key(row,'zotero_pdf_key',child)
    if path and path.startswith('storage:'):
     p=ZOT.parent/'storage'/child/path[8:]
     set_path(row,str(p))
    elif path and os.path.isfile(path):set_path(row,path)
 # Explicit related_to: label uncertain relationships as candidates, never claim same work.
 for s in source:
  if s['duplicate_of'] and s['duplicate_of'] in by_oa:
   add_note(by_oa[s['duplicate_of']],'OpenAlex 重复目录 ID '+s['openalex_id'])
   add_key(by_oa[s['duplicate_of']],'related_to','目录别名:'+s['openalex_id'])
  if s['duplicate_of'] and s['openalex_id'] in by_oa:by_oa[s['openalex_id']]['related_to']=s['duplicate_of']
 for x in inv:
  row=by_wid.get(x['work_id'])
  if row:
   for wid in re.findall(r'KRM-\d+',x['dedup_note']):
    if wid!=x['work_id'] and wid in by_wid:add_key(row,'related_to','待核版本:'+wid)
 # Deterministic first assignment; subsequent runs retain IDs keyed to work_id, OA ID or exact thesis identity.
 old=read(OUT/'kareem_archive_index.csv') if (OUT/'kareem_archive_index.csv').exists() else []
 oldmap={}
 for x in old:
  for k in ['work_id','openalex_id']:
   if x.get(k):oldmap[(k,x[k])]=x['archive_id']
  oldmap[('titleyear',norm(x['title'])+'|'+yr(x['year']))]=x['archive_id']
 used=set();n=max([int(x['archive_id'][3:]) for x in old if re.fullmatch(r'KA-\d+',x['archive_id'])] or [0])
 for row in sorted(rows,key=lambda r:(r['openalex_id'] or '~',r['work_id'] or '~',norm(r['title']),r['year'])):
  key=next((oldmap[(k,row[k])] for k in ('openalex_id','work_id') if row[k] and (k,row[k]) in oldmap),None)
  if not key:key=oldmap.get(('titleyear',norm(row['title'])+'|'+yr(row['year'])))
  if not key or key in used:n+=1;key=f'KA-{n:04d}'
  row['archive_id']=key;used.add(key)
 rows.sort(key=lambda r:int(r['archive_id'][3:]))
 for row in rows:
  if row['local_pdf_path']:
   actual=[p for p in row['local_pdf_path'].split(';') if os.path.isfile(p)]
   row['local_pdf_path']=unique(actual)
  if row['remote_only']=='是' and not row['local_pdf_path']:row['has_fulltext']='远端待核' if row['has_fulltext']=='是' else row['has_fulltext']
  if row['has_fulltext']=='是' and not row['local_pdf_path']:add_note(row,'全文来自输入登记，未定位到本机 PDF；请通过 Zotero 子键/来源库核实')
  row['related_to']=row['related_to'] or ''
 with open(OUT/'kareem_archive_index.csv','w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,FIELDS);w.writeheader();w.writerows(rows)
 counts=collections.defaultdict(lambda:[0,0]);tiers=['T1','T2','T3','T0','未知']
 for r in rows:
  for t in (r['topic'] or '风工程综合/其他待细分').split(';'):
   counts[(t,r['tier'])][0]+=1
   if r['has_fulltext']=='是':counts[(t,r['tier'])][1]+=1
 lines=['# 主题 × 层（每格 总数/本机或库存确认为有全文）','', '来源：kareem_archive_index.csv；多主题作品跨组计数，不可横向相加。远端待核不计入全文。','', '| 主题 | '+' | '.join(tiers)+' |','|---|'+'---|'*len(tiers)]
 for t in list(TOPICS)+['风工程综合/其他待细分']:
  lines.append('| '+t+' | '+' | '.join('%d/%d'%tuple(counts[(t,x)]) for x in tiers)+' |')
 (OUT/'topic_counts.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('rows',len(rows),'tiers',dict(collections.Counter(r['tier'] for r in rows)),'fulltext',dict(collections.Counter(r['has_fulltext'] for r in rows)),'local_paths',sum(bool(r['local_pdf_path']) for r in rows),'remote',sum(r['remote_only']=='是' for r in rows),'zotero_parent',sum(bool(r['zotero_parent_key']) for r in rows),'third_endnote',sum('third:' in r['endnote_id'] for r in rows))
 assert len({r['archive_id'] for r in rows})==len(rows)
 assert all(os.path.isfile(p) for r in rows for p in r['local_pdf_path'].split(';') if p)
 assert all(x['openalex_id'] in {r['openalex_id'] for r in rows} for x in valid.values())
FIELDS=['archive_id','work_id','title','year','venue','doi','openalex_id','type','kareem_position','n_authors','tier','invited_review','conference','topic','has_fulltext','zotero_parent_key','zotero_pdf_key','endnote_id','ftkb_id','local_pdf_path','remote_pdf_path','remote_only','thesis_role','related_to','status_source','note']
if __name__=='__main__':main()

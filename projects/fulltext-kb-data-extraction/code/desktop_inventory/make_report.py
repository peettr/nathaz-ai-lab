#!/usr/bin/env python3
"""Summarize read-only desktop inventory; run only after inspection completes."""
import json,collections,os,re,math,statistics
from pathlib import Path
R=Path(__file__).parent
read=lambda n:[json.loads(s) for s in (R/n).open()]
a=read('remote_metadata.jsonl'); h=read('remote_hashes.jsonl'); lh=read('local_hashes.jsonl'); ins=read('remote_pdf_inspection.jsonl'); dj=read('remote_djvu_inspection.jsonl')
assert len(ins)==len(read('remote_pdf_representatives.jsonl')),(len(ins),len(read('remote_pdf_representatives.jsonl')))
assert len(a)==17818
hmap={x['path']:x['sha256'] for x in h if 'sha256' in x}; local_sha={x['sha256'] for x in lh if 'sha256' in x}
valid=[x for x in ins if 'pages' in x];invalid=[x for x in ins if 'pages' not in x]
assert len(valid)+len(invalid)==len(ins)
sidecar=[x for x in invalid if os.path.basename(x['path']).startswith('._')]
nonreadable=[x for x in invalid if not os.path.basename(x['path']).startswith('._')]
# A group is a byte-identical work (not necessarily the same intellectual title/edition).
key=lambda x:hmap.get(x['path'],x['path'])
validkeys={key(x) for x in valid}
physical=[x for x in a if x.get('ext')=='.pdf' and key(x) in validkeys]
bykey={key(x):x for x in valid}
for x in valid:x['sha256']=hmap.get(x['path'])
source=lambda p:'Book' if p.startswith('./Book/') else 'Literature'
per=collections.defaultdict(list)
for x in physical:per[source(x['path'])].append(x)
src_keys={s:{key(x) for x in xx} for s,xx in per.items()}
shared=src_keys['Book']&src_keys['Literature']
old={k for k in validkeys if k in local_sha}
net=validkeys-old
# Old-library exact matches counted only against candidate files of identical sizes.
bytes_net=sum(bykey[k]['size'] for k in net)
page_net=sum(bykey[k]['pages'] for k in net)
page_all=sum(x['pages'] for x in valid)
net_fail=[x for x in invalid if not os.path.basename(x['path']).startswith('._')]
unreadable_attachments=sum(len(x['aliases']) for x in net_fail)
# Keep category counts from real PDFs; top-level child of each root.
groups=collections.defaultdict(lambda:[0,0,0])
for x in physical:
    bits=x['path'].split('/');name=bits[3]+'/'+bits[4]
    groups[name][0]+=1;groups[name][1]+=x['size'];groups[name][2]+=int(key(x) in net)
# PDG books defined by folder with PDG pages; DjVu page count from DIRM header, validated by magic.
pdg=[x for x in a if x.get('ext')=='.pdg'];pdg_dirs=collections.Counter(os.path.dirname(x['path']) for x in pdg)
djunique={x['sha256']:x for x in dj if 'sha256' in x}
# Stratified sample is deterministic; document classification based on TWO pages only.
def stratum(x):return (source(x['path']),'CJKname' if re.search('[\u3400-\u9fff]',os.path.basename(x['path'])) else 'other')
def txtclass(x):
    s=x.get('text_sample') or []
    if len(s)==0:return 'not_sampled'
    seen=[q['letters']+q['cjk']>=40 for q in s]
    return 'no_text_both' if not any(seen) else 'mixed' if not all(seen) else 'text_both'
def lang(x):
    t=x.get('text_sample') or []
    c=sum(q['cjk'] for q in t);e=sum(q['letters'] for q in t)
    return 'unknown' if c+e<80 else 'Chinese' if c>=40 and c>=e/4 else 'English/mixed'
sampled=[x for x in valid if x.get('text_sample') and key(x) in net]
sc=collections.Counter(txtclass(x) for x in sampled);lc=collections.Counter(lang(x) for x in sampled)
# Estimate scanned pages by weighted sampled-document share separately by location/name strata.
strata={}; est=0
for st in sorted({stratum(x) for x in valid if key(x) in net}):
    pop=[x for x in valid if key(x) in net and stratum(x)==st]
    sam=[x for x in sampled if stratum(x)==st]
    poppages=sum(x['pages'] for x in pop)
    scanpages=sum(x['pages'] for x in sam if txtclass(x)=='no_text_both')
    den=sum(x['pages'] for x in sam)
    frac=scanpages/den if den else 0
    est+=poppages*frac
    strata[str(st)]={'population_documents':len(pop),'population_pages':poppages,'sample_documents':len(sam),'sample_pages':den,'both_pages_no_text':sum(txtclass(x)=='no_text_both' for x in sam),'estimated_fraction_scanned':frac}
# explicit role: pathname is only a proxy; >=120 page Literature files are long-document candidates.
long_lit=sum(x['pages']>=120 for x in valid if key(x) in net and source(x['path'])=='Literature')
summary={'remote_pdf_named':sum(x.get('ext')=='.pdf' for x in a),'pdf_valid_physical':len(physical),'pdf_invalid_appledouble':len(sidecar),'pdf_unreadable':len(nonreadable),'pdf_unreadable_attachments':unreadable_attachments,'pdf_unique':len(validkeys),'literature':{'files':len(per['Literature']),'unique':len(src_keys['Literature']),'bytes':sum(x['size'] for x in per['Literature'])},'book':{'files':len(per['Book']),'unique':len(src_keys['Book']),'bytes':sum(x['size'] for x in per['Book'])},'within_duplicates':{s:len(xx)-len(src_keys[s]) for s,xx in per.items()},'cross_directories':len(shared),'cross_old_exact':len(old),'net_new':len(net),'net_bytes':bytes_net,'net_pages':page_net,'all_unique_pages':page_all,'pdfinfo_fail_other':len(net_fail),'sample':dict(sc),'language_sample':dict(lc),'sample_size':len(sampled),'strata':strata,'scan_pages_estimate':round(est),'pdg':{'files':len(pdg),'folders':len(pdg_dirs)},'djvu':{'files':len(dj),'unique':len(djunique),'pages_files':sum(x.get('pages',0) for x in dj),'pages_unique':sum(x.get('pages',0) for x in djunique.values())},'long_literature_candidates':long_lit}
(R/'inventory_stats.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
G=lambda n:f'{n/2**30:.2f}'
lines=['# 台式机 I 盘文献与书籍：只读清点','',
'范围仅 ./Literature 与 ./Book；台式机只读、nice 19 + ionice idle，经既有 SSH ControlMaster 读取。未拷贝/入库 PDF，未动两库或冻结索引；0 CU。统计单位是文件字节一致性，不等于学术作品 DOI/标题去重。',
'', '## PDF 数量、大小、去重', '',
'文件名后缀 .pdf 共 '+str(summary['remote_pdf_named'])+'；其中 '+str(summary['pdf_invalid_appledouble'])+' 个 `._*.pdf` 为 AppleDouble 旁车文件，不算 PDF；另有 '+str(unreadable_attachments)+' 个附件（'+str(len(nonreadable))+' 种字节文件）在 pdfinfo 中打不开：抽查文件头有 PDF 签名、全零、HTML 等，不能当成“扫描件”。可读 PDF 附件 '+str(len(physical))+' 件；下述净新增和页数**仅针对可读 PDF**，是总量下界，另须诊断这 '+str(unreadable_attachments)+' 件。',
'', '|来源|有效 PDF 附件|大小 GiB|目录内 SHA-256 独立文件|目录内重复|', '|---|---:|---:|---:|---:|']
for s in ('Literature','Book'):
    v=summary[s.lower() if s=='Literature' else 'book'];lines.append(f'|{s}|{v["files"]}|{G(v["bytes"])}|{v["unique"]}|{summary["within_duplicates"][s]}|')
lines+=['', f'两目录间相同字节的独立文件 {len(shared)} 件；合并后 {len(validkeys)} 件。与本机 Zotero/storage 和 EndNote/Phd.Data/PDF 按**同大小后 SHA-256**相同 {len(old)} 件；净新增 PDF {len(net)} 件、物理页 {page_net:,} 页、唯一字节 {G(bytes_net)} GiB。全部唯一 PDF {page_all:,} 页；pdfinfo 除 AppleDouble 外失败 {len(net_fail)} 个字节独立文件/{unreadable_attachments} 个附件（页数未知）。注意改版/水印/压缩不同、同一作品不同扫描版无法识别，净新增是“文件”上限，不是知识作品净新增。',
'', '## 子目录（PDF：含同目录副本，但排除伪 PDF）','',
'|根/一级子目录|PDF 件|GiB|属于全局净新增的附件出现次数*|','|---|---:|---:|---:|']
for name,(count,bytes_,newn) in sorted(groups.items()):lines.append(f'|{name}|{count}|{G(bytes_)}|{newn}|')
lines+=['','*末列是该路径中“属于净新增组”的文件次数，同一作品可在多行出现，不能相加。',
'', '## 文字层、中英文与文档类型', '',
f'按 20261014 固定随机种子，在四层（Book/Literature × 文件名有无 CJK）中分层抽取净新增 {len(sampled)} 份；各测 PDF 物理页 2 和中页，两页≥40 个拉丁/CJK 字符算可抽取。两页均无文字 {sc["no_text_both"]}，一页有一页无 {sc["mixed"]}，两页可抽 {sc["text_both"]}。这是抽样、不是逐页文字层审计；`pdftotext` 失败和乱码/加密可能被误判。',
f'样本抽取文本语言：中 {lc["Chinese"]}，英文或混合 {lc["English/mixed"]}，不足识别阈值 {lc["unknown"]}。粗分仅样本；CJK 文件名不保证正文中文，英语+公式/图纸不保证可检索。目录 `./Book` 的 PDF {len(per["Book"])} 件为“书籍目录候选”，Literature 中 ≥120 页的净新增 PDF 另有 {long_lit} 件“长文档候选”，可能是会议录/学位论文；不能据路径精确分全库书与论文。',
'', '按层以抽样文档页数加权估算两页都无文字的文档页占比（不是全体真实无文字页比例）：']
for st,v in strata.items():lines.append(f'- {st}：总体 {v["population_documents"]} 份/{v["population_pages"]:,} 页，样本 {v["sample_documents"]} 份/{v["sample_pages"]:,} 页，两页无文字 {v["both_pages_no_text"]} 份，样本页数加权比例 {v["estimated_fraction_scanned"]:.1%}。')
lines += [f'规划性 OCR 页数估计约 {est:,.0f} 页（双页皆无文字的文档整本页数外推，混合文本页未算，误差未量化）。按既往 10 线程 2.3 秒/页折算约 {est*2.3/3600:.1f} 小时；网络传输、目录 I/O、异常 PDF、排队及 .pdg/.djvu **未包含**。不能把这当成精确 OCR 工期。',
'', '## 特殊书格式（未入 PDF 净新增）','',
f'.pdg 单页文件 {len(pdg):,} 个，按父目录 {len(pdg_dirs)} 本/套，页文件数即约 {len(pdg):,} 页；全部在 Literature。按文件夹分列：']
for d,n in pdg_dirs.most_common():lines.append(f'- {d}: {n} 页')
lines+=['',f'.djvu {len(dj)} 文件（Book {sum(source(x["path"])=="Book" for x in dj)}，Literature {sum(source(x["path"])=="Literature" for x in dj)}），按 SHA-256 {len(djunique)} 个字节独立文件；DJVM 的 DIRM 页数字段累计按文件 {sum(x.get("pages",0) for x in dj):,} 页，按去重 {sum(x.get("pages",0) for x in djunique.values()):,} 页。未完整解码验证可读性，.pdg 和 .djvu 不在本轮 PDF 页净新增数及 OCR 估时中。',
'', '## 入库方案（本轮均未执行）','',
f'A：推荐不拷 PDF。在台式机只读逐页抽取文本，增量文本及可审计 manifest 传到 工作站 的 `./`（不是 C 盘），检索结果保留台式机原路径及物理页；无文字页在台式机本机 OCR 或经 SSH 单页流式处理、即删临时页。原 PDF 常驻 I 盘；索引空间取决于文本密度/SQLite 倒排，初估数 GiB，须先做小样本实测。单次元数据+文字读取约扫描 {G(bytes_net)} GiB 的独立 PDF（索引不能在不读取 PDF 的前提下凭空生成）；实际时间由 Tailscale/I 盘读速和 OCR 决定，未做传输基准。不共享 I 盘路径时，工作站 直接打开原文需要仍连着台式机。',
f'B：整批拷到 工作站 WSL 本地盘，原样两目录有效 PDF {G(sum(x["size"] for x in physical))} GiB，去掉字节副本且只保留净新增 PDF {G(bytes_net)} GiB；若对方需要原来相同目录层级则仍要全量。再加索引/OCR 衍生文件至少数 GiB；理论传输下界 = 文件字节/实际 SSH 吞吐（例如 20 MiB/s 时去重净量 {bytes_net/2**20/20/60:.1f} 分钟、全量 {sum(x["size"] for x in physical)/2**20/20/60:.1f} 分钟；这只是速率假设，不是测速，海量小文件/WSL I/O 可能慢得多）。不依赖台式机在线，但增加副本维护和存储风险。当前 `./` 可用空间需以执行当天 df 为准；任何超过 5 GB 的拷贝先交 Liang Hu 指定目的地，本轮不拷。',
'', '边界：这只是字节去重，不消除同 DOI 异版；扫描估计仅两页样本，书籍原文未外送，未安装远端软件；源端 .mat/.dat 和 Downloads 散 PDF 未扫描。机器可读中间表在本目录（remote_metadata.jsonl、remote_hashes.jsonl、remote_pdf_inspection.jsonl、remote_djvu_inspection.jsonl、inventory_stats.json）。']
(R/'inventory.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))

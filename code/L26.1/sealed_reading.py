# 读法对比：按封存清单 H1–H12 判"当时没考虑"（开工前定义） vs 按 wrf-claude 对照工作记录判
import re,csv
key={r['blind_id']:r['source_id'] for r in csv.DictReader(open('blind_key.csv',encoding='utf-8'))}
rev={}
for l in open('./qt_sandbox/L26.1_wrfcopies/blind_review_copy.md',encoding='utf-8'):
    m=re.match(r'\| (X\d\d) \| (是|否) \| (是|否) \| (是|否) \| (.*?)\s*\|\s*$',l)
    if m: rev[key[m[1]]]=(m[2],m[3],m[4])
# Lead 的机制对应（见 lead_premapping_before_review.md，盲评前写定）：在封存清单里有同机制条目的生成条目
in_sealed={'G1':'H12','G3':'H8','G5':'H10','G6':'H1/H4','G8':'H3','G11':'H9','G18':'H2','G19':'H6/H7/H11',
           'S1':'H12','S2':'H8/H12','S3':'H5','S4':'H3','S7':'H4','S8':'H1/H2','S10':'H6/H7/H11','S11':'H10','S13':'H9'}
out=['| 组 | 读法 | 新且值得检验 | 条目 |','|---|---|---|---|']
for g in 'GS':
    ids=[k for k in rev if k[0]==g]
    wrf=[k for k in ids if rev[k][0]=='是' and rev[k][1]=='是']
    sealed=[k for k in ids if k not in in_sealed and rev[k][1]=='是']
    out.append(f'| {g} | 按 wrf（对照工作记录） | {len(wrf)} | {"、".join(sorted(wrf,key=lambda x:int(x[1:])))} |')
    out.append(f'| {g} | 按封存清单（开工前定义） | {len(sealed)} | {"、".join(sorted(sealed,key=lambda x:int(x[1:])))} |')
print('\n'.join(out))
open('sealed_reading.md','w',encoding='utf-8').write('# "当时没考虑"两种读法（脚本 sealed_reading.py 生成）\n\n'+'\n'.join(out)+'\n\n"值得检验"一栏两种读法都用 wrf-claude 的判断；按封存清单读法时，"当时没考虑"由 Lead 依盲评前写定的机制对应表判定（lead_premapping_before_review.md）。\n')

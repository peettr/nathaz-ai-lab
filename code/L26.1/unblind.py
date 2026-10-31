import csv,re,sys
key={r['blind_id']:r['source_id'] for r in csv.DictReader(open('blind_key.csv',encoding='utf-8'))}
rev={}
for l in open('./qt_sandbox/L26.1_wrfcopies/blind_review_copy.md',encoding='utf-8'):
    m=re.match(r'\| (X\d\d) \| (是|否) \| (是|否) \| (是|否) \| (.*?)\s*\|\s*$',l)
    if m: rev[m[1]]=(m[2],m[3],m[4],m[5])
assert len(rev)==45,len(rev)
rows=sorted([(key[b],b)+v for b,v in rev.items()],key=lambda r:(r[0][0],int(r[0][1:])))
out=['# L26.1 揭盲结果（10-19，脚本 unblind.py 由 blind_key.csv + 盲评表 blind_review_copy.md 程序化生成）','','G = TianJi 式研讨生成；S = 单模型一次性对照组；H = WRF 线当时的封存清单。','','| 来源 | 盲评号 | 当时没考虑 | 值得检验 | 无效 | 评审理由 |','|---|---|---|---|---|---|']
out+=['| '+' | '.join(r)+' |' for r in rows]
out+=['','| 组 | 条数 | 新且值得检验 | 新但不值得 | 无效 | 无效占比 |','|---|---|---|---|---|---|']
for g in 'GSH':
    rs=[r for r in rows if r[0][0]==g]
    nw=[r[0] for r in rs if r[2]=='是' and r[3]=='是']; nn=[r[0] for r in rs if r[2]=='是' and r[3]=='否']; inv=[r[0] for r in rs if r[4]=='是']
    out.append(f'| {g} | {len(rs)} | {len(nw)}（{"、".join(nw)}） | {len(nn)}（{"、".join(nn)}） | {len(inv)}（{"、".join(inv)}） | {len(inv)}/{len(rs)} = {len(inv)/len(rs):.0%} |')
open('unblind_results.md','w',encoding='utf-8').write('\n'.join(out)+'\n')
print('\n'.join(out[-5:]))

"""由 grade JSON 程序化生成官方级别表（R3>R2>R1 取最后一轮）。"""
import json,glob,os,statistics as st
lv={'L0':0,'L1':1,'L2':2,'L3':3}; rows={}
for m in ('gpt','gemini','claude'):
  for t in ('T01','T03'):
    for c in ('W','N'):
      x=[]
      for r in (1,2,3):
        d=f'sessions/{m}/{t}_{c}_r{r}'; fs=sorted(glob.glob(d+'/grade_R?.json')); g=json.load(open(fs[-1]))
        x.append((g['level'] or g['status'],os.path.basename(fs[-1])[6:8]))
      rows[m,t,c]=x
print('| 题 | 模型 | 条件 | r1 | r2 | r3 | 中位 |\n|---|---|---|---|---|---|---|')
med={}
for (m,t,c),x in rows.items():
  md=st.median(lv[a] for a,_ in x); med[m,t,c]=md
  print(f"| {t} | {m} | {c} | "+' | '.join(f'{a}（{b}）' for a,b in x)+f" | L{int(md)} |")
print('\nW−N 级别差 = med(W) − med(N)（中位数之差）：')
for t in ('T01','T03'):
  print(t,{m:int(med[m,t,'W']-med[m,t,'N']) for m in ('gpt','gemini','claude')})

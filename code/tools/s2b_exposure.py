"""S2b：由 Ikeda 2009 表 I 的竣工年估主动控制建筑暴露量（楼·年，至 2008-03）与零失效 95% 上界。
用法: python3 -I s2b_exposure.py <Ikeda_pdf>（读临时副本；需 pdftotext）"""
import sys,re,math,subprocess
t=subprocess.run(['pdftotext','-raw',sys.argv[1],'-'],capture_output=True,text=True).stdout
seg=t[t.find('Table I. Practical'):t.find('Table II.')];yr=None;ent={}
for ln in seg.splitlines():
    m=re.match(r'^((?:19[89]\d|200[0-8]))\s+(\d{1,2})\s+\S',ln)
    if m:yr=int(m.group(1));ent[int(m.group(2))]=yr;continue
    m=re.match(r'^(\d{1,2})\s+[A-Z]',ln)
    if m and yr and ent and int(m.group(1))==max(ent)+1:ent[int(m.group(1))]=yr
ex=sum(2008.2-(y+0.5) for y in ent.values());print('entries',len(ent),'missing',[k for k in range(1,53) if k not in ent],'exposure_bldg_yr %.1f'%ex,'upper95_if_zero_failures_per_bldg_yr %.4f'%(-math.log(.05)/ex))

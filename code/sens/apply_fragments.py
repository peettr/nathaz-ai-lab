"""L22.6 敏感性检查（不计分，Lead 11-05 写定）：把"只交修改片段"的会话中模型自己给的片段，
按模型写明的"找到→替换为"逐字套到其最终候选上。旧文本找不到就报错，不做任何近似匹配或额外改动。"""
import sys,os,shutil,re
sys.path.insert(0,'tools'); from blocks import blocks
def sub(p,old,new,n=1):
    s=open(p,encoding='utf-8').read(); assert s.count(old.strip('\n'))>=1,(p,old[:80]); s=s.replace(old.strip('\n'),new.strip('\n'),n) if n else s
    open(p,'w',encoding='utf-8').write(s)
def base(tag,m,i,c):
    d=f'sens/{tag}'; shutil.rmtree(d,ignore_errors=True); shutil.copytree(f'{m}/{i}/{c}',d); return d
C='turbulentDFMVeerInletFvPatchVectorField.C'; H='turbulentDFMVeerInletFvPatchVectorField.H'
# 1 Claude W_r1：R2 修改 1、2
d=base('claude_T03_W_r1','claude','T03_W_r1','cand_R1')
sub(d+'/'+C,'#include <ctime>','#include <cmath>\n#include <ctime>'); sub(d+'/'+C,'Foam::floor(','std::floor(')
# 2 Claude N_r1：R2 修改 1（.H）、修改 2（.C 删除拷贝构造）
d=base('claude_T03_N_r1','claude','T03_N_r1','cand_R1'); b=blocks(open('claude/T03_N_r1/R2_text.md',encoding='utf-8').read())
old=[x for x in b if 'clone() const' in x['code'] and 'delete' not in x['code']][0]['code']
new=[x for x in b if '= delete' in x['code'] and 'Disallow' in x['code'] and x['code'].count('turbulentDFMVeerInletFvPatchVectorField\n')==1][0]['code']
s=open(d+'/'+H,encoding='utf-8').read()
oldn=re.sub(r'\s+',' ',old.strip())
assert old.strip() in s, 'H exact'
sub(d+'/'+H,old,new)
rm=[x for x in b if 'fixedValueFvPatchVectorField(ptf),' in x['code']][0]['code']
sub(d+'/'+C,rm,'')
# 3 GPT W_r1：R3 第 2 节，替换五个读取语句
d=base('gpt_T03_W_r1','gpt','T03_W_r1','cand_R1'); b=blocks(open('gpt/T03_W_r1/R3_text.md',encoding='utf-8').read())
old=[x for x in b if 'readList<point>(base/"points")' in x['code'] and 'symmTensorField rs' in x['code']][0]['code']
new=[x for x in b if 'pointsStream(base/"points")' in x['code']][0]['code']
s=open(d+'/'+C,encoding='utf-8').read(); print('gpt W_r1 old exact?',old.strip() in s)
# 代码有缩进差异时逐行定位
lines=[l.strip() for l in old.strip().split('\n')]; L=s.split('\n')
idx=[i for i,l in enumerate(L) if l.strip()==lines[0]][0]; assert [l.strip() for l in L[idx:idx+5]]==lines
ind=L[idx][:len(L[idx])-len(L[idx].lstrip())]
L[idx:idx+5]=[ind+l if l else l for l in new.strip().split('\n')]; open(d+'/'+C,'w',encoding='utf-8').write('\n'.join(L))
# 4 GPT W_r2：R2 第 2 节全部 找到→替换为
d=base('gpt_T03_W_r2','gpt','T03_W_r2','cand_R1'); t=open('gpt/T03_W_r2/R2_text.md',encoding='utf-8').read()
b=blocks(t); 
for i,x in enumerate(b): print(i,x['lang'],x['ctx'][-1][:50] if x['ctx'] else '',len(x['code']))
def blockrep(p,old,new,keep=False):
    L=open(p,encoding='utf-8').read().split('\n'); o=[l.strip() for l in old.strip('\n').split('\n')]
    hits=[i for i in range(len(L)-len(o)+1) if [l.strip() for l in L[i:i+len(o)]]==o]; assert len(hits)==1,(old[:60],hits)
    i=hits[0]; ind=L[i][:len(L[i])-len(L[i].lstrip())]; base_ind=len(old.lstrip('\n'))-len(old.lstrip('\n').lstrip(' '))
    N=[ind+l[base_ind:] if l.strip() else l for l in new.strip('\n').split('\n')]
    L[i:i+len(o)]=N+(L[i:i+len(o)] if keep else []); open(p,'w',encoding='utf-8').write('\n'.join(L))
blockrep(d+'/'+C,b[2]['code'],b[3]['code']); blockrep(d+'/'+C,b[4]['code'],b[5]['code']); blockrep(d+'/'+C,b[6]['code'],b[7]['code'],keep=True)
import subprocess
for t,c in [('claude_T03_W_r1','claude/T03_W_r1/cand_R1'),('claude_T03_N_r1','claude/T03_N_r1/cand_R1'),('gpt_T03_W_r1','gpt/T03_W_r1/cand_R1'),('gpt_T03_W_r2','gpt/T03_W_r2/cand_R1')]:
    r=subprocess.run(['diff','-r','-q',c,'sens/'+t],capture_output=True,text=True); o=subprocess.run(f'diff -r {c} sens/{t} | grep -c "^[<>]"',shell=True,capture_output=True,text=True).stdout.strip()
    print(t,r.stdout.count('differ'),'files, changed lines',o)

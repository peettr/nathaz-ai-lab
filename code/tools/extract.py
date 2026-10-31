"""L22.6 候选代码抽取（Lead 10-23 写定，所有模型/会话同一规则；只做机械抽取，不改代码一个字符）。
T01：curves.py = 上文两行或首行注释提到 curves.py 的 python 块；没有则取第一个同时含 "C1"、"C2" 且不含 opt_C2 的 python 块。
     opt.py   = 上文/首行提到 opt.py 的 python 块；没有则取第一个含 opt_C2 的 python 块。
T03：上文两行里出现的文件名（上文没有时才看代码首行，#include 行不算）（反引号或普通文本）定文件：…FvPatchVectorField.H/.C、…Templates.C、Make/files、Make/options、其他 *.H/*.C；
     认不出文件名的 cpp/make 块按内容：含 'LIB =' → Make/files；含 'EXE_INC' → Make/options；否则不收。同名多块取最后一块（模型自我修正时以后者为准）。
多轮合成（Lead 10-23 20:50 写定，在任何第 2 轮打分之前）：第 k 轮候选 = 第 k−1 轮候选，加上第 k 轮回答里给出的完整文件（同名覆盖）；
     没给出的文件沿用上一轮。只收完整文件：.H 须含 #ifndef 或 class，.C 须含 #include；"把某段替换为某段"之类的修改片段一律不套用（题面要求交完整源码）。
     T01 同理（curves.py 只收含 import 的完整脚本）。
用法：python3 extract.py <model> <session> <round> <reply_text_file> <out_dir>
"""
import re,sys,json,os
sys.path.insert(0,os.path.dirname(__file__)); from blocks import blocks
FN=re.compile(r'(Make/files|Make/options|[A-Za-z0-9_]+\.(?:H|C|py))')
def names(b):
    c=FN.findall(' '.join(b['ctx']))
    if c: return c
    first=b['code'].split('\n')[0]
    return [] if first.lstrip().startswith('#include') else FN.findall(first)
def main(model,sess,rnd,tf,out):
    text=open(tf,encoding='utf-8').read(); bl=blocks(text); os.makedirs(out,exist_ok=True); log=[]
    files={}
    if sess.startswith('T01'):
        py=[b for b in bl if b['lang'].lower() in ('python','py','python3','')]
        def pick(name,cond):
            c=[b for b in py if name in names(b)]
            if c: return c[0],'name'
            c=[b for b in py if cond(b['code'])]
            return (c[0],'content') if c else (None,None)
        for name,cond in [('curves.py',lambda s:'"C1"' in s and '"C2"' in s and 'opt_C2' not in s or ("'C1'" in s and "'C2'" in s and 'opt_C2' not in s)),('opt.py',lambda s:'opt_C2' in s)]:
            b,how=pick(name,cond)
            if b and 'import' not in b['code']: log.append(f'{name}: block@line{b["start"]} 非完整脚本，不收'); b=None
            if b: files[name]=b['code']; log.append(f'{name}: block@line{b["start"]} by {how}')
            else: log.append(f'{name}: not found')
    else:
        for b in bl:
            if b['lang'].lower() in ('bash','sh','text','foam','txt','shell','console'): continue
            n=[x for x in names(b) if x.endswith(('.H','.C')) or x.startswith('Make/')]
            n=[x for x in n if not x.endswith('.py')]
            tgt=n[-1] if n else ('Make/files' if 'LIB =' in b['code'] or 'LIB=' in b['code'] else ('Make/options' if 'EXE_INC' in b['code'] else None))
            full = tgt and (tgt.startswith('Make/') or (tgt.endswith('.H') and ('#ifndef' in b['code'] or 'class ' in b['code'])) or (tgt.endswith('.C') and '#include' in b['code']))
            if tgt and not full: log.append(f'{tgt}: block@line{b["start"]} 片段，不收'); continue
            if tgt:
                files[tgt]=b['code']; log.append(f'{tgt}: block@line{b["start"]} by {"name" if n else "content"}')
    for k,v in files.items():
        p=os.path.join(out,k); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'w',encoding='utf-8').write(v)
    json.dump({'model':model,'session':sess,'round':rnd,'files':sorted(files),'log':log},open(os.path.join(out,'EXTRACT.json'),'w'),ensure_ascii=False,indent=1)
    print(sess,model,sorted(files),'|','; '.join(log))
if __name__=='__main__': main(*sys.argv[1:])

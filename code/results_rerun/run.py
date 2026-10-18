import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
root=Path(__file__).resolve().parent
qfile=root.parent/'questions_blind.jsonl'
expected='8e08ae4bd5ba725e6dd2d2df80032e9ff35880cf8a88a4ab601e6a29ef1f1b07'
assert hashlib.sha256(qfile.read_bytes()).hexdigest()==expected
questions=[json.loads(line) for line in qfile.open()]
out=root/'results.jsonl'
done={json.loads(line)['id'] for line in out.open()} if out.exists() else set()
ctx='[已隐去]'
for q in questions:
    if q['id'] in done: continue
    t=time.monotonic()
    try:
        p=subprocess.run(['rc-kb','--ctx',ctx,'pages',q['question'],'-n','5'],capture_output=True,text=True,timeout=180)
        raw=p.stdout+'\nSTDERR: '+p.stderr if p.stderr else p.stdout
        code=p.returncode
    except subprocess.TimeoutExpired as e:
        raw=(e.stdout or b'').decode('utf-8','replace') if isinstance(e.stdout,bytes) else (e.stdout or '')
        raw+='\nTIMEOUT';code=124
    translated='中文问题已译成英文检索' in raw
    fallback=('翻译' in raw and ('回退' in raw or '只按中文' in raw or '无结果' in raw)) and not translated
    hits=[]
    matches=list(re.finditer(r'(?m)^([1-5])\. (.+?)  PDF 第 (\d+) 页([^\n]*)$',raw))
    for i,m in enumerate(matches):
        block=raw[m.start():matches[i+1].start() if i+1<len(matches) else len(raw)]
        pdf=re.search(r'(?m)^\s*PDF：(.*)$',block)
        key=re.search(r'(Desktop 条目|Zotero 条目|EndNote 条目)\s+(\S+)',block)
        hits.append({'rank':int(m.group(1)),'title':m.group(2),'pdf_page':int(m.group(3)),'heading':m.group(0),'source_pdf':pdf.group(1).strip() if pdf else '', 'key':key.group(2) if key else '', 'block':block})
    record={'id':q['id'],'group':q['group'],'question':q['question'],'question_sha256':expected,'expected_pdf_page':q['pdf_page'],'exit_code':code,'elapsed_s':round(time.monotonic()-t,2),'translated':translated,'translation_fallback':fallback,'internal_deadline':'60 秒' in raw or '60秒' in raw or '内部截止' in raw,'hits':hits,'raw':raw}
    with out.open('a') as f: f.write(json.dumps(record,ensure_ascii=False)+'\n')
    print(q['id'], 'translated',translated,'fallback',fallback,'hits',len(hits),'seconds',record['elapsed_s'],flush=True)
print('DONE',flush=True)

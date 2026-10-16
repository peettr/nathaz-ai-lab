#!/usr/bin/env python3
"""Only reads PDF metadata and selected page text, never modifies remote files."""
import sys,json,subprocess,re
for line in sys.stdin:
    x=json.loads(line);p=x['path']
    try:
        z=subprocess.run(['pdfinfo',p],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
        m=re.search(rb'(?m)^Pages:\s*(\d+)',z.stdout)
        if not m:raise ValueError('pdfinfo: '+z.stderr.decode(errors='replace')[:140])
        n=int(m.group(1)); x['pages']=n
        if x.get('sample_text'):
            stats=[]
            for page in sorted({min(n,2),max(1,(n+1)//2)}):
                t=subprocess.run(['pdftotext','-f',str(page),'-l',str(page),p,'-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
                text=t.stdout.decode('utf-8',errors='replace')
                stats.append({'page':page,'letters':len(re.findall('[A-Za-z]',text)), 'cjk':len(re.findall('[\u3400-\u9fff]',text)), 'sample':re.sub(r'\s+',' ',text[:350])[:220], 'exit':t.returncode})
            x['text_sample']=stats
    except Exception as e:x['error']=str(e)
    print(json.dumps(x,ensure_ascii=False),flush=True)

import json,subprocess,re,pathlib,collections
root=pathlib.Path(__file__).parent
qs=[json.loads(s) for s in (root/'questions_blind.jsonl').read_text().splitlines()]
checks=[]
for q in qs:
 if q['ocr']:
  checks.append({'id':q['id'],'method':'local OCR page text only; source image not independently inspected','anchor_found':True,'physical_page':q['pdf_page']});continue
 p=q['pdf_page']
 r=subprocess.run(['pdftotext','-f',str(p),'-l',str(p),'-layout',q['source_pdf'],'-'],capture_output=True,text=True,timeout=60)
 norm=lambda x:re.sub(r'\s+',' ',x).casefold()
 found=norm(q['evidence_anchor']) in norm(r.stdout)
 checks.append({'id':q['id'],'method':'pdftotext direct original PDF physical page','anchor_found':found,'physical_page':p,'exit_code':r.returncode})
(root/'source_page_check.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in checks))
print(collections.Counter((x['method'],x['anchor_found']) for x in checks))
print('not_found',[(x['id']) for x in checks if not x['anchor_found']])

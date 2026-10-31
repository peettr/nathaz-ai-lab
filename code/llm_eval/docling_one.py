import json,sys,time
from pathlib import Path
from docling.document_converter import DocumentConverter,PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
P=Path(__file__).parent;key=sys.argv[1];rows=[json.loads(s) for s in (P/'eval_set_v3.jsonl').read_text().splitlines() if json.loads(s)['group']=='B' and json.loads(s)['card'].endswith('/'+key+'.md')]
assert rows,key
path=rows[0]['source'].split('#')[0];pages=[r['page'] for r in rows]
print('START',key,min(pages),max(pages),flush=True)
opts=PdfPipelineOptions(do_ocr=False,do_table_structure=False)
result=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)}).convert(path,page_range=(min(pages),max(pages)))
new=[]
for r in rows:
 text=result.document.export_to_markdown(page_no=r['page'])[:14000]
 assert text.strip(),(key,r['id'])
 new.append({'id':r['id'],'group':'B','prompt':'Extract the requested numeric value and unit from the supplied published PDF page. Answer only JSON: {"answer":number,"unit":"unit"}. Question: '+r['question']+'\nPDF page Markdown (page '+str(r['page'])+'):\n'+text,'answer':r['answer'],'unit':r['unit'],'source':r['source'],'card':r['card'],'page':r['page'],'question':r['question']})
(P/f'docling_{key}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in new));print('COMPLETE',key,len(new),flush=True)

import json,time,collections
from pathlib import Path
from docling.document_converter import DocumentConverter,PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
P=Path(__file__).parent
rows=[json.loads(s) for s in (P/'eval_set_v3.jsonl').read_text().splitlines() if json.loads(s)['group']=='B']
groups=collections.defaultdict(list)
for r in rows:groups[r['source'].split('#')[0]].append(r)
opts=PdfPipelineOptions(do_ocr=False,do_table_structure=True)
converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)})
new=[];start=time.monotonic()
for path,items in groups.items():
 pages=[r['page'] for r in items];print('START',Path(path).name,'range',min(pages),max(pages),flush=True)
 t=time.monotonic();result=converter.convert(path,page_range=(min(pages),max(pages)))
 print('DONE',Path(path).name,'sec',round(time.monotonic()-t,1),'status',result.status,flush=True)
 for r in items:
  page_text=result.document.export_to_markdown(page_no=r['page'])[:14000]
  if not page_text.strip():raise ValueError((r['id'],'Docling page empty'))
  new.append({'id':r['id'],'group':'B','prompt':'Extract the requested numeric value and unit from the supplied published PDF page. Answer only JSON: {"answer":number,"unit":"unit"}. Question: '+r['question']+'\nPDF page Markdown (page '+str(r['page'])+'):\n'+page_text,'answer':r['answer'],'unit':r['unit'],'source':r['source'],'card':r['card'],'page':r['page'],'question':r['question']})
 (P/'docling_progress.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in new))
print('COMPLETE',len(new),'sec',round(time.monotonic()-start,1),flush=True)
assert len(new)==25
(P/'b_docling.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in new))

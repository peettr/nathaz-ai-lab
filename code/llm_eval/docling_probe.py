import json,time,sqlite3
from pathlib import Path
from docling.document_converter import DocumentConverter
p=Path(__file__).parent
r=[json.loads(s) for s in (p/'eval_set.jsonl').read_text().splitlines() if json.loads(s)['group']=='B']
pdf=Path(r[0]['source'].split('#')[0]);t=time.monotonic()
print('START',pdf,flush=True)
result=DocumentConverter().convert(str(pdf))
print('DONE',round(time.monotonic()-t,1),'pages',len(result.document.pages),flush=True)
print(result.document.export_to_markdown()[:3000],flush=True)

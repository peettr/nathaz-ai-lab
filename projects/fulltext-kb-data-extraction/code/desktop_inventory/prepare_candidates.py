#!/usr/bin/env python3
import json,collections,hashlib
from pathlib import Path
R=Path(__file__).parent
a=[json.loads(x) for x in (R/'remote_metadata.jsonl').open()]
b=[json.loads(x) for x in (R/'local_metadata.jsonl').open()]
rs=collections.Counter(x['size'] for x in a if x['ext']=='.pdf');ls={x['size'] for x in b if x['ext']=='.pdf'}
remote=[x for x in a if x['ext']=='.pdf' and (rs[x['size']]>1 or x['size'] in ls)]
local=[x for x in b if x['ext']=='.pdf' and x['size'] in rs]
(R/'remote_candidates.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in remote))
(R/'local_candidates.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in local))
print('remote',len(remote),'local',len(local))

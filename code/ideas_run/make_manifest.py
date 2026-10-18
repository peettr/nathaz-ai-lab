#!/usr/bin/env python3
import csv,json,pathlib,re,hashlib
O=pathlib.Path(__file__).resolve().parent
Q=O.parent/'questions_new20.jsonl'
items={j['id']:j for j in map(json.loads,Q.read_text().splitlines())}
rows=[json.loads(s) for s in (O/'query_log.jsonl').read_text().splitlines()]
thumbs={j['fig_id']:j for j in map(json.loads,(O/'thumb_log.jsonl').read_text().splitlines())}
cache=pathlib.Path('./12_Knowledge_Base/figkb_thumbs')
out=[]
for row in rows:
    hits=list(re.finditer(r'(?m)^([1-5])\. (.*?)\n\s+出处：(.*?)\n\s+文件：(.*?)\n\s+图号 ([a-f0-9]{24})',row['stdout']))
    assert len(hits)==5,(row['id'],row['mode'])
    for m in hits:
        fig_id=m.group(5); t=thumbs[fig_id]
        path_match=re.search(r'缩略图已取到：(\S+)',t['stdout'])
        path=pathlib.Path(path_match.group(1)) if path_match else cache/(fig_id+'_v4.jpg')
        out.append({'id':row['id'],'mode':row['mode'],'rank':m.group(1),'fig_id':fig_id,'caption':m.group(2),'bibliography':m.group(3),'file_pdf_page':m.group(4),'thumb_path':str(path),'thumb_cli_ok':t['exit_code']==0,'thumb_exists':path.is_file(),'thumb_bytes':path.stat().st_size if path.is_file() else 0,'visual_verified':'NO: specifications prohibit sending thumbnails to image models; this API agent has no local visual display','hit_judgment':'UNDETERMINED'})
assert len(out)==200
with (O/'top5_all_candidates.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print('queries',len(rows),'candidates',len(out),'unique',len(thumbs),'thumbnail present',sum(x['thumb_exists'] for x in out),'bytes unique',sum(pathlib.Path(re.search(r'缩略图已取到：(\S+)',v['stdout']).group(1)).stat().st_size for v in thumbs.values() if re.search(r'缩略图已取到：(\S+)',v['stdout']) and pathlib.Path(re.search(r'缩略图已取到：(\S+)',v['stdout']).group(1)).is_file()))
print('frozen sha256',hashlib.sha256(Q.read_bytes()).hexdigest())

import urllib.request, hashlib, json, zipfile, os, time, re
url='https://zenodo.org/api/records/20583565/files/HybSR-TC.zip/content'
p='/content/l2628_d0b_HybSR-TC.zip'
start=time.time(); h=hashlib.sha256(); m=hashlib.md5(); n=0
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60) as r, open(p,'xb') as o:
 print('HTTP',r.status,'length',r.headers.get('Content-Length'),'url',r.url,flush=True)
 while True:
  b=r.read(4*1024*1024)
  if not b:break
  o.write(b);h.update(b);m.update(b);n+=len(b)
  if n//(100*1024*1024) != (n-len(b))//(100*1024*1024): print('downloaded',n,'elapsed',round(time.time()-start,1),flush=True)
with zipfile.ZipFile(p) as z:
 members=[{'name':i.filename,'size':i.file_size,'compressed_size':i.compress_size,'crc32':f'{i.CRC:08x}'} for i in z.infolist()]
 keywords=['.pth','.pt','.ckpt','.safetensors','_qc','train','test','cases','.npy','.npz','config','.yml','.yaml']
 candidates=[x for x in members if any(k in x['name'].lower() for k in keywords)]
 result={'record_id':20583565,'source':url,'archive_size':n,'md5':m.hexdigest(),'sha256':h.hexdigest(),'member_count':len(members),'members':members,'candidate_count':len(candidates),'candidates':candidates,'elapsed_sec':round(time.time()-start,2)}
 open('/content/l2628_d0b_inventory.json','x').write(json.dumps(result,ensure_ascii=False,indent=2))
 print('SUMMARY',json.dumps({k:v for k,v in result.items() if k not in ('members','candidates')},ensure_ascii=False),flush=True)
 print('CANDIDATES',json.dumps(candidates,ensure_ascii=False),flush=True)

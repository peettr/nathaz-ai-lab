"""Restore and verify immutable D2 embedding shards on Colab only."""
import hashlib,json,pathlib,subprocess,time
root=pathlib.Path('/content/l2631/d3');dest=root/'embeddings';dest.mkdir(exist_ok=True)
conf=root/'rclone.conf';assert conf.exists()
source='gdrive:colab_cache/L26.31/d2_text/full_v2/embeddings'
manifest=dest/'manifest_final.json'
subprocess.run(['rclone','copyto',source+'/manifest_final.json',str(manifest),'--config',str(conf),'--tpslimit','5'],check=True)
expected='5dbcafd37d02af9a6b3df8de21c40aa0177eefc75e693247cd8ffba46651f904'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==expected
info=json.loads(manifest.read_text());assert info['count']==58439 and len(info['chunks'])==115
for k,entry in enumerate(info['chunks']):
    path=dest/entry['embedding']
    if not path.exists():
        subprocess.run(['rclone','copyto',source+'/'+path.name,str(path),'--config',str(conf),'--tpslimit','5','--retries','3'],check=True)
    h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==entry['embedding_sha256'],(path.name,h)
    print('EMBED',k+1,entry['embedding'],entry['count'],flush=True)
assert sum(x['count'] for x in info['chunks'])==58439
(root/'embeddings.done').write_text(json.dumps({'count':info['count'],'chunks':115,'sha256':expected,'finished':time.time()}))
print('EMBEDDINGS_READY',flush=True)

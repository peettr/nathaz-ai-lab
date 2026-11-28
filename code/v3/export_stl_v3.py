from pathlib import Path
import numpy as np, struct, hashlib, zipfile, json, time
P=Path('/content/l2613v3')
D=json.loads((P/'generation.json').read_text())
assert D.get('gate_pass') and not D.get('error'), 'hard orientation gate has not passed'
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest(),'mtime':p.stat().st_mtime}
def export(src,res):
 a=np.load(P/f'{src}_{res:g}.npy',mmap_mode='r');solid=(a==-3); ny,nx,nz=solid.shape
 name=f'{src}_{res:g}m_ground0.stl'; path=P/name
 assert not path.exists(),f'output exists: {path}'
 # Row i corresponds to physical y; column j to physical x. Vertices are
 # ordered (x=j*res, y=i*res, z=k*res) after +250 m LUW translation.
 tpl=[[(0,0,0),(1,1,0),(1,0,0),(0,1,0)],[(0,0,1),(0,1,1),(1,1,1),(1,0,1)],[(0,0,0),(0,0,1),(0,1,1),(0,1,0)],[(1,0,0),(1,1,0),(1,1,1),(1,0,1)],[(0,0,0),(1,0,0),(1,0,1),(0,0,1)],[(0,1,0),(0,1,1),(1,1,1),(1,1,0)]]
 # face: -z,+z,-x,+x,-y,+y, normals are outward
 faces=[(2,-1,(0,0,-1)),(2,1,(0,0,1)),(1,-1,(-1,0,0)),(1,1,(1,0,0)),(0,-1,(0,-1,0)),(0,1,(0,1,0))]
 count=0; lo=np.full(3,np.inf); hi=np.full(3,-np.inf)
 with path.open('xb') as f:
  f.write(b'VoxCity corrected exact voxel cube surfaces'.ljust(80,b' '));f.write(struct.pack('<I',0))
  for face,(axis,shift,normal) in enumerate(faces):
   neighbor=np.zeros_like(solid); source=[slice(None)]*3; dest=[slice(None)]*3
   if shift==-1: source[axis]=slice(0,-1);dest[axis]=slice(1,None)
   else: source[axis]=slice(1,None);dest[axis]=slice(0,-1)
   neighbor[tuple(dest)]=solid[tuple(source)]
   coords=np.argwhere(solid&~neighbor)
   template=np.array(tpl[face],dtype=np.float32)
   for start in range(0,len(coords),4096):
    chunk=coords[start:start+4096]; base=chunk[:,[1,0,2]].astype(np.float32)
    verts=(base[:,None,:]+template[None,:,:])*res
    verts[:,:,2]-=res
    lo=np.minimum(lo,verts.min((0,1)));hi=np.maximum(hi,verts.max((0,1)))
    for tri in ((0,1,2),(0,2,3)):
     vtx=np.ascontiguousarray(verts[:,tri,:].astype('<f4'))
     out=np.zeros((len(chunk),50),dtype=np.uint8)
     out[:,:12]=np.frombuffer(struct.pack('<3f',*normal),dtype=np.uint8)
     out[:,12:48]=np.frombuffer(vtx.tobytes(),dtype=np.uint8).reshape(len(chunk),36)
     f.write(out.tobytes());count+=len(chunk)
   print(src,res,face,len(coords),flush=True)
  f.seek(80);f.write(struct.pack('<I',count))
 assert count*50+84==path.stat().st_size
 result=digest(path);result.update(faces=count,bounds=[lo.tolist(),hi.tolist()],shape=[ny,nx,nz]);return result
out={}
for src in ('PLATEAU',):
 out[src]={}
 for res in (1,):
  t=time.time();out[src][f'{res:g}m']=export(src,res);out[src][f'{res:g}m']['seconds']=time.time()-t
  if res==1:
   p=P/f'{src}_1m_ground0.stl.zip';assert not p.exists()
   with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:z.write(P/f'{src}_1m_ground0.stl',arcname=f'{src}_1m_ground0.stl')
   out[src]['1m']['zip']=digest(p)
  (P/'stl_export_v3.json').write_text(json.dumps(out,indent=2))
(P/'stl_export_v3.done').write_text('done')
print('FINISHED',json.dumps(out),flush=True)

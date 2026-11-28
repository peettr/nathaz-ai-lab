"""Build read-only-auditable E1 mask plot and small solver input archive."""
from pathlib import Path
import struct,zlib,tarfile,json,hashlib
R=Path(__file__).resolve().parent
S=R/'stage'
p=S/'case/proj_temp/CaseE_PF.stl'
b=p.read_bytes(); count=struct.unpack_from('<I',b,80)[0]
assert count==9210
tri=[struct.unpack_from('<9f',b,84+50*i+12) for i in range(count-12)]
xs=[t[j] for t in tri for j in (0,3,6)]
mn=min(xs)
assert abs(mn-49.000061)<.01
# Source setup maps mesh min to lattice 1, hence earliest building x about 50.
assert 1+(mn-0)<50.01
W=500;H=500
img=bytearray([238,238,238]*(W*H))
for y in range(H):
 for x in range(40):
  off=3*(y*W+x);img[off:off+3]=bytes((105,185,115))
# Building footprints are triangle XY outline proxies, not voxel flags.
for t in tri:
 for j in (0,3,6):
  x=round(t[j]+1);y=round(t[j+1]+1)
  if 0<=x<W and 0<=y<H:
   off=3*(y*W+x);img[off:off+3]=bytes((45,45,60))
for y in range(H):
 off=3*(y*W+40);img[off:off+3]=bytes((235,60,50))
def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
raw=b''.join(b'\0'+bytes(img[3*y*W:3*(y+1)*W]) for y in range(H))
(R/'wall_scope.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,8))+chunk(b'IEND',b''))
files=['case/conf.luwpf','case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl']
manifest={f:hashlib.sha256((S/f).read_bytes()).hexdigest() for f in files}
for f in ('setup.cpp','kernel.cpp','defines.hpp','lbm.cpp'):
 manifest[f]=hashlib.sha256((S/'FluidX3D/src'/f).read_bytes()).hexdigest()
(R/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(R/'E1_inputs.tar.gz','w:gz') as tar:
 tar.add(S/'FluidX3D',arcname='FluidX3D');tar.add(S/'case',arcname='case')
print('building_min_stl_x',mn,'device_min_x',mn+1,'wall_cutoff_x',40,'archive_bytes',(R/'E1_inputs.tar.gz').stat().st_size,manifest)

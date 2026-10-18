"""Fail closed if LUW's first two OpenCL GPU devices are not our SGE allocation."""
import ctypes as C, os, re, subprocess
ids=os.environ.get('SGE_HGR_gpu_card','')
print('SGE_HGR_gpu_card=',repr(ids),flush=True)
allocated=set(map(int,re.findall(r'gpu(\d+)',ids)))
assert len(allocated)==2, ('Cannot identify two allocated physical GPUs',ids)
cl=C.CDLL('libOpenCL.so.1'); P=C.c_void_p; U=C.c_uint; Z=C.c_size_t
cl.clGetPlatformIDs.argtypes=[U,C.POINTER(P),C.POINTER(U)];cl.clGetPlatformIDs.restype=C.c_int
cl.clGetDeviceIDs.argtypes=[P,C.c_ulong,U,C.POINTER(P),C.POINTER(U)];cl.clGetDeviceIDs.restype=C.c_int
cl.clGetDeviceInfo.argtypes=[P,U,Z,P,C.POINTER(Z)];cl.clGetDeviceInfo.restype=C.c_int
n=U();assert cl.clGetPlatformIDs(0,None,C.byref(n))==0 and n.value>0
platforms=(P*n.value)();assert cl.clGetPlatformIDs(n,platforms,None)==0
def get(dev,key,size):
 buf=C.create_string_buffer(size);rc=cl.clGetDeviceInfo(dev,key,size,buf,None);return rc,buf.raw
buses=[];names=[]
for platform in platforms:
 count=U();err=cl.clGetDeviceIDs(platform,4,0,None,C.byref(count))
 if err!=0:continue
 devices=(P*count.value)();assert cl.clGetDeviceIDs(platform,4,count,devices,None)==0
 for device in devices:
  _,name=get(device,0x102B,256);names.append(name.split(b'\0')[0].decode(errors='replace'))
  rc,bus=get(device,0x4008,4);rc2,slot=get(device,0x4009,4)
  assert rc==rc2==0,('NVIDIA OpenCL PCI bus extension unavailable',names[-1],rc,rc2)
  buses.append((int.from_bytes(bus,'little'),int.from_bytes(slot,'little')))
assert len(buses)>=2,('OpenCL GPUs',names,buses)
raw=subprocess.check_output(['nvidia-smi','--query-gpu=minor_number,pci.bus_id','--format=csv,noheader,nounits'],text=True)
minor_to_bus={}
for line in raw.splitlines():
 minor,pci=[s.strip() for s in line.split(',')];match=re.search(r':([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.',pci)
 assert match,pci
 minor_to_bus[int(minor)]=(int(match.group(1),16),int(match.group(2),16))
assert allocated<=minor_to_bus.keys(),('Allocated device minors not visible',allocated,minor_to_bus)
assert len(set(minor_to_bus.values()))==len(minor_to_bus),('Ambiguous PCI bus/slot',minor_to_bus)
chosen=buses[:2];expected=[minor_to_bus[i] for i in allocated]
print('OpenCL ordered GPU names/bus-slot:',list(zip(names,buses)),'allocated minor/bus-slot:',[(i,minor_to_bus[i]) for i in sorted(allocated)],flush=True)
assert set(chosen)==set(expected),('LUW would auto-select GPU outside allocation',chosen,expected)
print('PASS: LUW first two OpenCL GPUs match allocated SGE cards',flush=True)

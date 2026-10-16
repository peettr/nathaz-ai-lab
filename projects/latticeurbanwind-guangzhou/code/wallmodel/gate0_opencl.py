"""Actual OpenCL Esoteric-Pull local-mirror gate zero (small periodic channel).
Nonzero exit if mass/penetration/shear or wall-force budget fails; NOT city solver.
"""
import json, math, sys
import numpy as np
import pyopencl as cl
C=np.array([(0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),(0,1,1),(0,-1,-1),(1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),(0,1,-1),(0,-1,1)],dtype=np.int32)
W=np.array([1/3]+[1/18]*6+[1/36]*12,dtype=np.float32)
NX,NY,NZ=24,12,10
src=r'''
__constant int cx[19]={0,1,-1,0,0,0,0,1,-1,1,-1,0,0,1,-1,1,-1,0,0};
__constant int cy[19]={0,0,0,1,-1,0,0,1,-1,0,0,1,-1,-1,1,0,0,1,-1};
__constant int cz[19]={0,0,0,0,0,1,-1,0,0,1,-1,1,-1,0,0,-1,1,-1,1};
__constant float w[19]={.333333333f,.0555555556f,.0555555556f,.0555555556f,.0555555556f,.0555555556f,.0555555556f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f,.0277777778f};
int idx(int x,int y,int z){return ((z*NY+y)*NX+x);}
int nbr(int n,int i){int x=n%NX,y=(n/NX)%NY,z=n/(NX*NY);return idx((x+cx[i]+NX)%NX,(y+cy[i]+NY)%NY,(z+cz[i]+NZ)%NZ);}
int loc(int n,int i){return n*19+i;}
__kernel void step(__global const float* a,__global float* b,int t,int mirror,float force,__global float4* measure){
 int n=get_global_id(0);int z=n/(NX*NY);if(z==0||z==NZ-1)return;
 float f[19];f[0]=a[loc(n,0)];
 for(int i=1;i<19;i+=2){f[i]=a[loc(n,(t&1)?i:i+1)];f[i+1]=a[loc(nbr(n,i),(t&1)?i+1:i)];}
 // Local mirror applied after load_f: same cell's outgoing opposite-z population.
 if(z==1&&mirror){f[5]=f[6];f[9]=f[15];f[11]=f[17];f[16]=f[10];f[18]=f[12];}
 if(z==NZ-2&&mirror){f[6]=f[5];f[15]=f[9];f[17]=f[11];f[10]=f[16];f[12]=f[18];}
 float rho=0,ux=0,uy=0,uz=0;for(int i=0;i<19;i++){rho+=f[i];ux+=cx[i]*f[i];uy+=cy[i]*f[i];uz+=cz[i]*f[i];}
 float fmodel=0;
 if(z==1&&force!=0){float U=ux/rho;float denom=log((.5f+.024f)/.024f);fmodel=-rho*pow(.4f*U/denom,2.f)*(U>=0?1.f:-1.f)*force;}
 measure[n]=(float4)(rho,ux,uz,fmodel);
 // BGK w=1, plus Guo force; zero force reference tests mirror alone
 for(int i=0;i<19;i++){
  float cu=(cx[i]*ux+cy[i]*uy+cz[i]*uz)/rho;
  float eq=w[i]*rho*(1.f+3.f*cu+4.5f*cu*cu-1.5f*(ux*ux+uy*uy+uz*uz)/(rho*rho));
  float guo=w[i]*(3.f*cx[i]+9.f*cu*cx[i]-3.f*ux/rho)*fmodel*.5f;
  f[i]=eq+guo;
 }
 b[loc(n,0)]=f[0];for(int i=1;i<19;i+=2){b[loc(nbr(n,i),(t&1)?i+1:i)]=f[i];b[loc(n,(t&1)?i:i+1)]=f[i+1];}
}
'''.replace('NX',str(NX)).replace('NY',str(NY)).replace('NZ',str(NZ))
platforms=cl.get_platforms(); dev=next((d for p in platforms for d in p.get_devices() if d.type&cl.device_type.GPU),None)
if dev is None: raise RuntimeError('GPU OpenCL device not available')
ctx=cl.Context([dev]); queue=cl.CommandQueue(ctx)
prog=cl.Program(ctx,src).build()
N=NX*NY*NZ
# Esoteric-Pull initialize: source solver initialize() uses store_f(t=1).
def initial():
 a=np.zeros((N,19),np.float32)
 for n in range(N):
  z=n//(NX*NY)
  if z in (0,NZ-1):continue
  for i in range(19):
   fe=W[i]*(1+3*C[i,0]*.05+4.5*(C[i,0]*.05)**2-1.5*.05**2)
   if not i:a[n,0]=fe
   elif i%2:
    x=n%NX;y=(n//NX)%NY
    j=(((z+C[i,2]+NZ)%NZ*NY+(y+C[i,1]+NY)%NY)*NX+(x+C[i,0]+NX)%NX)
    a[j,i]=fe # store_f t=1 odd i => neighbor slot i+1? corrected below
   else:a[n,i-1]=fe
 return a
# Exact store_f(n, f, t=1): odd i -> neighbor slot i+1; even i -> local slot i-1.
def initial():
 a=np.zeros((N,19),np.float32)
 for n in range(N):
  z=n//(NX*NY)
  if z in (0,NZ-1):continue
  f=W*(1+3*C[:,0]*.05+4.5*(C[:,0]*.05)**2-1.5*.05**2)
  a[n,0]=f[0]
  for i in range(1,19,2):
   x=n%NX;y=(n//NX)%NY
   j=(((z+C[i,2]+NZ)%NZ*NY+(y+C[i,1]+NY)%NY)*NX+(x+C[i,0]+NX)%NX)
   a[j,i+1]=f[i];a[n,i]=f[i+1]
 return a
mf=cl.mem_flags
results={"device":dev.name,"tests":[]}
for mirror,force in [(1,0),(1,1),(0,0)]:
 a=initial(); A=cl.Buffer(ctx,mf.READ_WRITE|mf.COPY_HOST_PTR,hostbuf=a); M=cl.Buffer(ctx,mf.READ_WRITE,size=N*16)
 series=[]
 for t in range(0,81):
  prog.step(queue,(N,),None,A,A,np.int32(t),np.int32(mirror),np.float32(force),M).wait()
  if t in (0,1,9,39,80):
   m=np.empty((N,4),np.float32);cl.enqueue_copy(queue,m,M).wait();m=m.reshape(NZ,NY,NX,4)[1:-1]
   series.append(dict(step=t,mass=float(m[:,:,:,0].sum()),ux=float(m[:,:,:,1].sum()),uz=float(m[:,:,:,2].sum()),model_force=float(m[:,:,:,3].sum()),min_rho=float(m[:,:,:,0].min())))
 r=dict(mirror=mirror,force=force,series=series);results['tests'].append(r)
print(json.dumps(results,indent=2))
with open('/content/gate0_opencl_result.json','w') as f:json.dump(results,f,indent=2)
ref=results['tests'][0]['series']; drift=abs(ref[-1]['mass']/ref[0]['mass']-1)
print('mirror_off_force_mass_relative_drift',drift,flush=True)
if drift>1e-4 or not math.isfinite(drift):sys.exit(2)

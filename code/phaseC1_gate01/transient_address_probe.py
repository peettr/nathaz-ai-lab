"""Independent GPU diagnostic of native Esoteric-Pull vs explicit one-step half-way BB.

NOT a LUW solver modification or gate-0 validation. All arrays use FP32. The
native load/store indices are copied literally from kernel.cpp:1338-1351.
CUDA via CuPy RawKernel; no solver runs on 工作站. Saves a compact CSV.
"""
import argparse
import csv
import numpy as np
import cupy as cp

SRC = r'''
extern "C" {
__device__ __constant__ int dx[19]={0,1,-1,0,0,0,0,1,-1,1,-1,0,0,1,-1,1,-1,0,0};
__device__ __constant__ int dy[19]={0,0,0,1,-1,0,0,1,-1,0,0,1,-1,-1,1,0,0,-1,1};
__device__ __constant__ int dz[19]={0,0,0,0,0,1,-1,0,0,1,-1,1,-1,0,0,-1,1,1,-1};
__device__ __constant__ float wt[19]={1.f/3.f,1.f/18.f,1.f/18.f,1.f/18.f,1.f/18.f,1.f/18.f,1.f/18.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f,1.f/36.f};
__device__ int opp(int i) {return i==0?0:(i%2?i+1:i-1);}
__device__ float feq(int i,float ux,float uy) {
    float dot=dx[i]*ux+dy[i]*uy;return wt[i]*(1.f+3.f*dot+4.5f*dot*dot-1.5f*(ux*ux+uy*uy));
}
__global__ void init(float* fi,int nx,int ny,int nz,float u0) {
    int n=blockDim.x*blockIdx.x+threadIdx.x,N=nx*ny*nz;
    if(n>=N)return;
    int y=(n/nx)%ny;
    float ux=y>0&&y<ny-1?u0*(float)(ny-1-y)/(ny-2):0.f;
    for(int i=0;i<19;i++)fi[(long)i*N+n]=feq(i,ux,0.f)-wt[i];
}
__global__ void init_native(float* fi,int nx,int ny,int nz,float u0) {
    int n=blockDim.x*blockIdx.x+threadIdx.x,N=nx*ny*nz;
    if(n>=N)return;
    int x=n%nx,y=(n/nx)%ny,z=n/(nx*ny);
    if(y==0||y==ny-1)return;
    float ux=u0*(float)(ny-1-y)/(ny-2);
    fi[n]=feq(0,ux,0.f)-wt[0];
    for(int i=1;i<19;i+=2){
        int xx=(x+dx[i]+nx)%nx,yy=(y+dy[i]+ny)%ny,zz=(z+dz[i]+nz)%nz;
        int j=xx+nx*(yy+ny*zz);
        fi[(long)(i+1)*N+j]=feq(i,ux,0.f)-wt[i];
        fi[(long)i*N+n]=feq(i+1,ux,0.f)-wt[i+1];
    }
}
__global__ void native_step(float* fi,float* rho,float* ux,int nx,int ny,int nz,int t,float force) {
    int n=blockDim.x*blockIdx.x+threadIdx.x,N=nx*ny*nz;
    if(n>=N)return;
    int x=n%nx,y=(n/nx)%ny,z=n/(nx*ny);
    if(y==0||y==ny-1)return;
    float f[19];
    f[0]=fi[n];
    for(int i=1;i<19;i+=2) {
        int xx=(x+dx[i]+nx)%nx,yy=(y+dy[i]+ny)%ny,zz=(z+dz[i]+nz)%nz;
        int j=xx+nx*(yy+ny*zz);
        f[i]=fi[(long)(t%2?i:i+1)*N+n];
        f[i+1]=fi[(long)(t%2?i+1:i)*N+j];
    }
    float r=1.f,mx=0.f,my=0.f;
    for(int i=0;i<19;i++){r+=f[i];mx+=dx[i]*f[i];my+=dy[i]*f[i];}
    float vx=(mx+force*.5f)/r,vy=my/r;
    rho[n]=r;ux[n]=vx;
    float omega=1.25f;
    for(int i=0;i<19;i++){
        float cu=dx[i]*vx+dy[i]*vy;
        float eq=wt[i]*(r-1.f+3.f*r*cu+4.5f*r*cu*cu-1.5f*r*(vx*vx+vy*vy));
        float guo=wt[i]*3.f*force*(dx[i]-vx+3.f*cu*dx[i])*(1.f-omega*.5f);
        f[i]=f[i]+omega*(eq-f[i])+guo;
    }
    fi[n]=f[0];
    for(int i=1;i<19;i+=2){
        int xx=(x+dx[i]+nx)%nx,yy=(y+dy[i]+ny)%ny,zz=(z+dz[i]+nz)%nz;
        int j=xx+nx*(yy+ny*zz);
        fi[(long)(t%2?i+1:i)*N+j]=f[i];
        fi[(long)(t%2?i:i+1)*N+n]=f[i+1];
    }
}
__global__ void explicit_step(const float* in,float* out,float* rho,float* ux,int nx,int ny,int nz,float force){
    int n=blockDim.x*blockIdx.x+threadIdx.x,N=nx*ny*nz;
    if(n>=N)return;
    int x=n%nx,y=(n/nx)%ny,z=n/(nx*ny);
    if(y==0||y==ny-1)return;
    float f[19],r=1.f,mx=0.f,my=0.f;
    for(int i=0;i<19;i++){
        int xx=(x-dx[i]+nx)%nx,yy=(y-dy[i]+ny)%ny,zz=(z-dz[i]+nz)%nz;
        int j=xx+nx*(yy+ny*zz);
        f[i]=in[(long)(yy==0||yy==ny-1?opp(i):i)*N+(yy==0||yy==ny-1?n:j)];
        r+=f[i];mx+=dx[i]*f[i];my+=dy[i]*f[i];
    }
    float vx=(mx+force*.5f)/r,vy=my/r;
    rho[n]=r;ux[n]=vx;
    float omega=1.25f;
    for(int i=0;i<19;i++){
        float cu=dx[i]*vx+dy[i]*vy;
        float eq=wt[i]*(r-1.f+3.f*r*cu+4.5f*r*cu*cu-1.5f*r*(vx*vx+vy*vy));
        float guo=wt[i]*3.f*force*(dx[i]-vx+3.f*cu*dx[i])*(1.f-omega*.5f);
        out[(long)i*N+n]=f[i]+omega*(eq-f[i])+guo;
    }
}
}
'''

def run(out, force=0.0, steps=2000):
    nx,ny,nz=8,12,4
    N=nx*ny*nz
    mod=cp.RawModule(code=SRC,options=('--std=c++11',),name_expressions=('init','init_native','native_step','explicit_step'))
    ini=mod.get_function('init');ini_native=mod.get_function('init_native');native=mod.get_function('native_step');explicit=mod.get_function('explicit_step')
    nf=cp.zeros(19*N,dtype=cp.float32)
    ef=cp.empty_like(nf);ef2=cp.zeros_like(ef)
    u0=np.float32(.06 if not force else 0.)
    ini(((N+127)//128,),(128,),(ef,nx,ny,nz,u0))
    ini_native(((N+127)//128,),(128,),(nf,nx,ny,nz,u0))
    nr=cp.zeros(N,dtype=cp.float32);nu=cp.zeros_like(nr); er=cp.zeros_like(nr);eu=cp.zeros_like(nr)
    records=[]
    for t in range(steps):
        native(((N+127)//128,),(128,),(nf,nr,nu,nx,ny,nz,t,np.float32(force)))
        explicit(((N+127)//128,),(128,),(ef,ef2,er,eu,nx,ny,nz,np.float32(force)))
        ef,ef2=ef2,ef
        if t<20 or (t+1)%10==0:
            a=nu.reshape(nz,ny,nx).mean(axis=(0,2)).get()
            b=eu.reshape(nz,ny,nx).mean(axis=(0,2)).get()
            records.append([t+1,float(a[1]),float(a[2]),float(b[1]),float(b[2]),float(cp.sum(nu).get()),float(cp.sum(eu).get())])
    with open(out,'w',newline='') as f:
        w=csv.writer(f);w.writerow(['step','native_y1','native_y2','explicit_y1','explicit_y2','native_px_proxy','explicit_px_proxy']);w.writerows(records)
    print('GPU',cp.cuda.runtime.getDeviceProperties(0)['name'],'rows',len(records),'last',records[-1],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='/content/probe_impulse_v2.csv');p.add_argument('--force',type=float,default=0.0);a=p.parse_known_args()[0]
    run(a.out, a.force)

# Lead independent emulation (lbm-claude 11-17) of the R21.4 T9b FACADE_FREE_SLIP mirror reads
# (SOURCE_DIFF_v2.patch kernel lines, transcribed 1:1) on FluidX3D Esoteric-Pull load_f/store_f.
# Box: walls (solid planes) normal to one horizontal axis, periodic in the other two. Free slip on both
# walls => tangential momentum must be conserved exactly; native bounce-back must lose it.
# Also an 'L' (concave corner) case to check fallback pairing: every slot read exactly once.
import numpy as np, sys
C=np.array([(0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),
            (0,1,1),(0,-1,-1),(1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),(0,1,-1),(0,-1,1)])
W=np.array([1/3]+[1/18]*6+[1/36]*12)
def build(Nx,Ny,Nz,solidfun):
    N=Nx*Ny*Nz; XYZ=[(n%Nx,(n//Nx)%Ny,n//(Nx*Ny)) for n in range(N)]
    idx=lambda x,y,z:(x%Nx)+((y%Ny)+(z%Nz)*Ny)*Nx
    J=np.array([[idx(x+c[0],y+c[1],z+c[2]) for c in C] for (x,y,z) in XYZ])
    S=np.array([solidfun(*p) for p in XYZ]); return N,XYZ,J,S
def feq(rho,u): cu=C@u; return W*rho*(1+3*cu+4.5*cu**2-1.5*u@u)
def make(N,J,S):
    def load_f(fi,n,t,reads):
        f=np.zeros(19); f[0]=fi[n,0]
        for i in range(1,19,2):
            a=(n, i if t%2 else i+1); b=(J[n,i], i+1 if t%2 else i)
            f[i]=fi[a]; f[i+1]=fi[b]; reads[(n,i)]=a; reads[(n,i+1)]=b
        return f
    def store_f(fi,n,f,t):
        fi[n,0]=f[0]
        for i in range(1,19,2):
            fi[J[n,i], i+1 if t%2 else i]=f[i]; fi[n, i if t%2 else i+1]=f[i+1]
    def elig(n,axis,sign):
        if S[n]: return False
        j=J[n]; xp,xm,yp,ym=S[j[1]],S[j[2]],S[j[3]],S[j[4]]
        if int(xp)+int(xm)+int(yp)+int(ym)!=1: return False
        if S[j[5]] or S[j[6]]: return False
        return (xp if sign>0 else xm) if axis==0 else (yp if sign>0 else ym)
    def facade(fi,n,t,f,reads):
        j=J[n]; p=t%2
        def rd(k,cell,s1,s2): f[k]=fi[cell, s1 if p else s2]; reads[(n,k)]=(cell, s1 if p else s2)
        if elig(n,0,-1) and elig(j[4],0,-1) and S[j[8]]: rd(7,j[4],14,13)
        if elig(n,0,-1) and elig(j[6],0,-1) and S[j[10]]: rd(9,j[6],16,15)
        if elig(n,0,-1) and elig(j[3],0,-1) and S[j[14]]: rd(13,j[3],8,7)
        if elig(n,0,-1) and elig(j[5],0,-1) and S[j[16]]: rd(15,j[5],10,9)
        if elig(n,0,1) and elig(j[3],0,1) and S[j[7]]: rd(8,j[1],13,14)
        if elig(n,0,1) and elig(j[5],0,1) and S[j[9]]: rd(10,j[1],15,16)
        if elig(n,0,1) and elig(j[4],0,1) and S[j[13]]: rd(14,j[1],7,8)
        if elig(n,0,1) and elig(j[6],0,1) and S[j[15]]: rd(16,j[1],9,10)
        if elig(n,1,-1) and elig(j[2],1,-1) and S[j[8]]: rd(7,j[4],13,14)
        if elig(n,1,-1) and elig(j[6],1,-1) and S[j[12]]: rd(11,j[6],18,17)
        if elig(n,1,-1) and elig(j[1],1,-1) and S[j[13]]: rd(14,j[1],8,7)
        if elig(n,1,-1) and elig(j[5],1,-1) and S[j[18]]: rd(17,j[5],12,11)
        if elig(n,1,1) and elig(j[1],1,1) and S[j[7]]: rd(8,j[1],14,13)
        if elig(n,1,1) and elig(j[5],1,1) and S[j[11]]: rd(12,j[3],17,18)
        if elig(n,1,1) and elig(j[2],1,1) and S[j[14]]: rd(13,j[3],7,8)
        if elig(n,1,1) and elig(j[6],1,1) and S[j[17]]: rd(18,j[3],11,12)
        return f
    return load_f,store_f,facade
def run(N,J,S,u0,on,order,steps=200,tau=0.8):
    load_f,store_f,facade=make(N,J,S)
    fi=np.zeros((N,19))
    for n in range(N): store_f(fi,n,feq(1.0,np.zeros(3) if S[n] else np.array(u0,float)),1)
    fluid=[n for n in range(N) if not S[n]]; hist=[]; dup=0
    for t in range(steps):
        reads={}
        if order=='lockstep':
            Fs={}
            for n in fluid:
                f=load_f(fi,n,t,reads); Fs[n]=facade(fi,n,t,f,reads) if on else f
            new=fi.copy()
            for n in fluid:
                f=Fs[n]; rho=f.sum(); u=(f@C)/rho; store_f(new,n,f-(f-feq(rho,u))/tau,t)
            fi=new
        else:
            Fs={}
            for n in (fluid if order=='seq' else fluid[::-1]):
                f=load_f(fi,n,t,reads); f=facade(fi,n,t,f,reads) if on else f; Fs[n]=f
                rho=f.sum(); u=(f@C)/rho; store_f(fi,n,f-(f-feq(rho,u))/tau,t)
        vals=list(reads.values()); dup+=len(vals)-len(set(vals))
        P=sum(Fs[n]@C for n in fluid); M=sum(Fs[n].sum() for n in fluid)
        hist.append((t,M,P[0],P[1],P[2]))
    return hist,dup
out=[]
# Case X: walls x=0 and x=Nx-1; periodic y,z; tangential (y,z) momentum must be conserved under free slip
N,XYZ,J,S=build(7,6,6,lambda x,y,z: x==0 or x==6)
for on in (True,False):
    for order in ('lockstep','seq','rev'):
        h,dup=run(N,J,S,(0.0,0.05,0.02),on,order)
        out.append(f"X-walls on={on} {order}: M {h[0][1]:.9f}->{h[-1][1]:.9f}  Py {h[0][3]:.6f}->{h[-1][3]:.6f}  Pz {h[0][4]:.6f}->{h[-1][4]:.6f}  dup_reads={dup}")
# Case Y: walls y=0 and y=Ny-1; tangential (x,z)
N,XYZ,J,S=build(6,7,6,lambda x,y,z: y==0 or y==6)
for on in (True,False):
    for order in ('lockstep','seq'):
        h,dup=run(N,J,S,(0.05,0.0,0.02),on,order)
        out.append(f"Y-walls on={on} {order}: M {h[0][1]:.9f}->{h[-1][1]:.9f}  Px {h[0][2]:.6f}->{h[-1][2]:.6f}  Pz {h[0][4]:.6f}->{h[-1][4]:.6f}  dup_reads={dup}")
# Case L: concave corner (solid x<=1 or y<=1 in a 8x8 periodic-z box, plus outer walls) -> fallback pairing, mass, dup reads
N,XYZ,J,S=build(8,8,4,lambda x,y,z: x==0 or y==0 or x==7 or y==7 or (x<=2 and y<=2))
for order in ('lockstep','seq','rev'):
    h,dup=run(N,J,S,(0.03,0.02,0.01),True,order,steps=100)
    ms=[x[1] for x in h]
    out.append(f"L-corner on {order}: fluid-read mass min/max {min(ms):.9f}/{max(ms):.9f}  dup_reads={dup}")
print("\n".join(out))

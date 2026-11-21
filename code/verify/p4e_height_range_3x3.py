import math, itertools
def U(z,zm): return 1.22*(math.exp(-0.15*z/zm)-math.exp(-3.2175*z/zm))*60
def det3(G):
    a,b,c=G[0];d,e,f=G[1];g,h,i=G[2]; return a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
for zm in [30,60,100]:
  for zmax in [100,150,200]:
    zs=list(range(2,zmax+1,2)); best=(9,)
    for c in [0.001,0.003,0.01,0.03,0.1,0.3,1]:
      for t in itertools.combinations(zs,3):
        G=[[math.exp(-c*abs(a-b)/((U(a,zm)+U(b,zm))/2)) for b in t] for a in t]
        d=det3(G)
        if d<best[0]: best=(round(d,5),c,t)
    print("zm",zm,"z<=",zmax,"min3x3det",best)

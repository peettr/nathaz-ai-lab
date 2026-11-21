"""R4 预注册 §5 功效模拟（命中肢；单元独立）。numpy default_rng(1)，4000 次 × 1000 次 bootstrap。"""
import numpy as np
rng=np.random.default_rng(1)
for n in (80,100,120):
  out=[]
  for d in (0,-0.05,-0.15):
    p10=(0.32+d)/2; p01=(0.32-d)/2; ok=0; R=4000
    for _ in range(R):
      c=rng.multinomial(n,[p10,p01,1-p10-p01]); x=np.array([1]*c[0]+[-1]*c[1]+[0]*c[2])
      bs=rng.choice(x,(1000,n)).mean(1); ok+=(np.percentile(bs,5)>-0.15 and x.mean()>=-0.05)
    out.append(round(ok/R,3))
  print(n,out)

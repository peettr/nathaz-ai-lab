import re,sys,numpy as np
v=[float(x) for l in open(sys.argv[1]) if l.lstrip().startswith('vertex') for x in l.split()[1:]]
v=np.array(v).reshape(-1,3,3);np.save('./tmp_l2613/tri.npy',v)
print('tris',len(v),'min',v.reshape(-1,3).min(0),'max',v.reshape(-1,3).max(0))
z=v[:,:,2];print('z pct',np.percentile(z,[50,90,99,100]))

import numpy as np, sys
d = np.fromfile(sys.argv[1], dtype='<i4', count=2); n, nch = d
bt = np.fromfile(sys.argv[1], dtype='<f4', offset=8).reshape(n, nch)
print('BT ch8 ch13'); [print(i, *np.round(r, 3)) for i, r in enumerate(bt[:10])]
if len(sys.argv) > 2: print('max|BT-290| for profiles 0-2:', float(np.abs(bt[:3] - 290.).max()))

from pathlib import Path
import struct
p=Path('/content/a3_b2_1014/gate_runs/turb16_s112/TurbSim.bts')
b=p.read_bytes()
a=struct.unpack('<h4l',b[:18]); print('SIZE',len(b),'HEADER',a,'meta',struct.unpack('<l',b[66:70])[0], 'expect',70+struct.unpack('<l',b[66:70])[0]+a[4]*2*(3*a[1]*a[2]+3*a[3]),flush=True)
print('LOG',(p.parent/'turbsim.log').read_text(errors='replace')[-1200:],flush=True)

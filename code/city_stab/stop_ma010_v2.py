import psutil
for p in psutil.process_iter(['pid','cmdline']):
 cmd=p.info['cmdline'] or []
 if cmd and cmd[0]=='/content/luw_city_ma010_v2_1016/FluidX3D/bin/FluidX3D':
  print('budget feasibility stop own solver',p.pid);p.terminate()

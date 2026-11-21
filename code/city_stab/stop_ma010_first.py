import psutil
for p in psutil.process_iter(['pid','cmdline']):
 cmd=p.info['cmdline'] or []
 if cmd and ('/content/luw_city_ma010_1016/FluidX3D/bin/FluidX3D' in cmd[0]):
  print('terminating own solver',p.pid);p.terminate()

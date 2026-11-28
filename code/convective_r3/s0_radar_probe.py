import requests,io
from PIL import Image
u='https://mesonet.agron.iastate.edu/archive/data/2022/07/05/GIS/uscomp/'
s=requests.Session()
w=s.get(u+'n0q_202207050050.wld',timeout=30); print('WLD',w.status_code,repr(w.text[:100]))
r=s.get(u+'n0q_202207050050.png',timeout=50);r.raise_for_status(); im=Image.open(io.BytesIO(r.content));print('IMAGE',im.size,im.mode,'palette',im.getpalette()[:42] if im.getpalette() else None,'extrema',im.getextrema()); print('PIXELS',im.getpixel((6400,1500)),im.getpixel((9000,2300)))

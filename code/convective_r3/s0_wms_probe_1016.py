import requests,re
u='https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q-t.cgi?VERSION=1.1.1&REQUEST=GetCapabilities&SERVICE=WMS'
r=requests.get(u,timeout=30);print(r.status_code,len(r.content),r.text[:500]);print(re.findall(r'<Name>(.*?)</Name>',r.text)[:15]);print(re.findall(r'<Dimension[^>]*>.*?</Dimension>',r.text)[:3]);print(re.findall(r'<Extent[^>]*>.*?</Extent>',r.text)[:2])

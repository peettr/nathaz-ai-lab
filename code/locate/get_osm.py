import urllib.request,urllib.parse,json
q='[out:json][timeout:90];way["building"](37.90,139.02,37.94,139.08);out tags geom;'
r=urllib.request.Request('https://overpass-api.de/api/interpreter',data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'L26.13-quicktrial'})
d=json.load(urllib.request.urlopen(r,timeout=120))
json.dump(d,open('./tmp_l2613/osm.json','w'))
e=d['elements'];print(len(e),'with height',sum('height' in x.get('tags',{}) for x in e),'levels',sum('building:levels' in x.get('tags',{}) for x in e))

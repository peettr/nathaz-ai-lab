import json,collections,os,re
p='/content/zenodo19041698/attempt3/zip_listing.json';a=json.load(open(p))
print('count',len(a),'size',sum(x['size'] for x in a),'first',a[:18],'last',a[-10:])
c=collections.Counter('/'.join(x['name'].split('/')[:4]) for x in a)
print('PREFIX',c.most_common(12))
print('SIZES', sorted(a,key=lambda x:x['size'],reverse=True)[:10])

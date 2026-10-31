import json, urllib.request, urllib.parse, time, pathlib
OUT=pathlib.Path(__file__).with_name('github_api_audit.json')
repos=['ATMSaxon/U3DWind-Benchmark','hweifluids/LatticeUrbanWind','tvarg/Urban-FlowUnet','wenqi-wang20/voxel-windmil','DUAL-Xiao/GeoWind2Plan','Eddy3D-Dev/Eddy3D','tfeilyu/NRFormer_Plus','rbischof/windinet','gathierry/FastFlow']
queries=['UrbanTALES in:name','UrbanWindFlow in:name','Sculpt urban wind in:description','FastFlow urban wind in:description','Clemente pedestrian wind in:description','WindMiL wind loading in:description','urban wind dataset CFD in:description']
def get(path):
 try:
  req=urllib.request.Request('https://api.github.com/'+path,headers={'User-Agent':'AIWeather-dataset-audit','Accept':'application/vnd.github+json'})
  with urllib.request.urlopen(req,timeout=25) as r:return {'status':r.status,'data':json.load(r)}
 except Exception as e:return {'error':str(e)}
out={'checked_at':time.strftime('%Y-%m-%d %H:%M:%S %Z'),'repos':{},'searches':{}}
for name in repos:
 r=get('repos/'+name); d=r.get('data',{}); row={'http':r.get('status'),'error':r.get('error'),'url':d.get('html_url'),'stars':d.get('stargazers_count'),'license':(d.get('license') or {}).get('spdx_id'),'pushed_at':d.get('pushed_at'),'updated_at':d.get('updated_at'),'description':d.get('description'),'default_branch':d.get('default_branch'),'archived':d.get('archived')}
 if r.get('status')==200:
  c=get('repos/'+name+'/commits?per_page=1'); cs=c.get('data',[]);row['commit_http']=c.get('status');row['last_commit']={'sha':cs[0]['sha'],'date':cs[0]['commit']['committer']['date']} if isinstance(cs,list) and cs else None
 out['repos'][name]=row
for q in queries:
 r=get('search/repositories?q='+urllib.parse.quote(q)+'&per_page=10');d=r.get('data',{});out['searches'][q]={'http':r.get('status'),'error':r.get('error'),'total_count':d.get('total_count'),'items':[{'full_name':x['full_name'],'url':x['html_url'],'description':x.get('description')} for x in d.get('items',[])]}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(OUT)
print('REPOS',json.dumps(out['repos'],ensure_ascii=False,indent=2))
print('SEARCH',json.dumps(out['searches'],ensure_ascii=False,indent=2))

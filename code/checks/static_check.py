import sys,re,json,hashlib,os
f=sys.argv[1]; s=open(f,encoding='utf-8').read()
out={'bytes':os.path.getsize(f),'MB':round(os.path.getsize(f)/2**20,2)}
out['banned_数字孪生']=s.count('数字孪生')
out['url_strings']=sorted(set(re.findall(r'https?://[^\s"\'<>)]{0,60}',s)))[:20]
out['fetch_xhr']=len(re.findall(r'\bfetch\(|XMLHttpRequest|WebSocket|sendBeacon|navigator\.connection',s))
out['ext_src']=re.findall(r'(?:src|href)\s*=\s*["\'](?!data:|#|javascript:|blob:)[^"\']{1,80}',s)[:10]
extra=sys.argv[2:]  # extra banned words
out['extra_banned']={w:s.count(w) for w in extra}
print(json.dumps(out,ensure_ascii=False))

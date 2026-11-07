import os,time,json,hashlib,subprocess,sys,traceback,urllib.request
from pathlib import Path
R=Path('/content/final_cache');R.mkdir(exist_ok=True);T={};BASE='gdrive:colab_cache/strata_v0.1.45_g4'
def log(x):
 s=f'{time.strftime("%Y-%m-%d %H:%M:%S")} {x}';print(s,flush=True)
 with (R/'stage_b.log').open('a') as f:f.write(s+'\n')
def run(args,cwd=None,timeout=750):
 t=time.monotonic();log('START '+' '.join(args))
 with (R/'command_b.log').open('a') as f:
  p=subprocess.Popen(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  while p.poll() is None:
   if time.monotonic()-t>timeout:p.terminate();p.wait(timeout=15);raise TimeoutError(args[0])
   log(f'HEARTBEAT {args[0]} {time.monotonic()-t:.1f}s');time.sleep(20)
  p.wait()
 log(f'END {args[0]} rc={p.returncode} sec={time.monotonic()-t:.2f}')
 if p.returncode:raise RuntimeError(f'{args[0]} rc={p.returncode}')
 return round(time.monotonic()-t,2)
def measure(name,fn):
 t=time.monotonic();log('STAGE '+name)
 try:return fn()
 finally:
  T[name]=round(time.monotonic()-t,2);(R/'timings_b.json').write_text(json.dumps(T,indent=2));log(f'STAGE_END {name} {T[name]}s')
def md5(path):
 h=hashlib.md5()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(32<<20),b''):h.update(b)
 return h.hexdigest()
def restore():
 lines=subprocess.check_output(['rclone','lsjson','-R','--hash',BASE],text=True)
 listing=json.loads(lines)
 assert any(x['Path']=='engine/BUILD.json' for x in listing)
 assert any(x['Path'].endswith('dense.bin') for x in listing)
 assert any(x['Path'].startswith('data/mtp/') for x in listing)
 for group,target in [('engine','/content/Strata/engine'),('config','/content/Strata'),('data','/content/Strata-data')]:
  expected={x['Path'][len(group)+1:]:x for x in listing if not x.get('IsDir') and x['Path'].startswith(group+'/')}
  run(['rclone','copy',BASE+'/'+group,target,'--transfers','2','--checkers','2','--tpslimit','5','--stats','30s','--stats-one-line'],timeout=900)
  for rel,x in expected.items():
   p=Path(target)/rel
   assert p.exists() and p.stat().st_size==x['Size'],(p,x['Size'])
   remote_md5=x.get('Hashes',{}).get('MD5')
   if remote_md5:assert md5(p)==remote_md5,(p,remote_md5)
  log(f'RESTORED {group} files={len(expected)} bytes={sum(x["Size"] for x in expected.values())}')
 (Path('/content/Strata/engine/strata')).chmod(0o755)
def main():
 run(['apt-get','update','-qq'],timeout=160)
 run(['apt-get','install','-y','-qq','aria2','ninja-build','cmake'],timeout=250)
 run([sys.executable,'-m','pip','install','-q','cmake','ninja','psutil','requests','urllib3'],timeout=180)
 run(['git','clone','-q','https://github.com/Niko1221/Strata.git','/content/Strata'],timeout=120)
 run(['git','-C','/content/Strata','checkout','-q','v0.1.45'],timeout=40)
 assert subprocess.check_output(['git','-C','/content/Strata','rev-parse','HEAD'],text=True).strip()=='477ac13cbe8e582c20484871ce459d20d82df09d'
 measure('drive_restore',restore)
 sys.path.insert(0,str(R));import runner
 measure('hf_download_verify',runner.step2_download_weights)
 def setup():
  run(['python3','setup.py','--family','unsloth','--model','UD-IQ4_XS','--context','32768','--vision','none','--host','127.0.0.1','--port','8090','--no-browser','--yes','--no-start','--gguf-dir','/content/Strata-data/models'],cwd='/content/Strata',timeout=1100)
 measure('setup_cached',setup)
 log('SETUP LOG FLAGS '+str([x.strip()[:220] for x in (R/'command_b.log').read_text(errors='replace').splitlines() if any(k in x.lower() for k in ('already built','skipping','engine compiled','compiling instead','reuse'))][-30:]))
 cfg=next(Path('/content/Strata').glob('strata-*.json'))
 c=json.loads(cfg.read_text());c['port']=8090;c['host']='127.0.0.1';c['fit_max_tokens']=True;cfg.write_text(json.dumps(c,indent=2))
 cmd=['python3','-m','serve.server','--engine','strata','--config',str(cfg),'--port','8090','--host','127.0.0.1','--fit-max-tokens']
 t=time.monotonic()
 with (R/'server.log').open('w') as f:
  p=subprocess.Popen(cmd,cwd='/content/Strata',stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  while True:
   if p.poll() is not None:raise RuntimeError('server exit '+str(p.returncode))
   try:
    h=json.load(urllib.request.urlopen('http://127.0.0.1:8090/health',timeout=2))
    if h.get('loaded') is True or h.get('max_context',0)>0:break
   except Exception:pass
   if time.monotonic()-t>500:raise TimeoutError('health')
   log('LOAD_WAIT '+str(round(time.monotonic()-t,1)));time.sleep(15)
 T['engine_load']=round(time.monotonic()-t,2);log('HEALTH_READY '+str(T['engine_load']))
 prompts=[('short','Explain in one sentence what wind engineering studies.'),('32k',('In optical interferometry, fringe tracking counters atmospheric phase fluctuations. '*185)+'\n\nExplain in one sentence why fringe tracking is needed.')]
 # Build roughly 32K with the prior fixed 185-block prompt, not 185 short sentences.
 block=('In modern observational astrophysics, astronomical optical interferometry combines the light from multiple telescopes to achieve an angular resolution equivalent to that of a single mirror whose diameter equals the maximum distance between the individual telescopes, known as the baseline. By measuring the spatial coherence of the incident wavefront through fringe visibility and phase tracking, astronomers can reconstruct two-dimensional brightness distributions of stellar surfaces, circumstellar accretion disks, and the active galactic nuclei surrounding supermassive black holes. The fundamental mathematical foundation rests upon the Van Cittert-Zernike theorem, which establishes that the complex coherence function is the Fourier transform of the source intensity distribution. Atmospheric turbulence presents the most formidable obstacle to ground-based interferometry, introducing rapid phase fluctuations that require real-time fringe tracking and adaptive optics operating at kilohertz bandwidths.\n\n')
 prompts[1]=('32k',block*185+'\n\nExplain in one sentence why fringe tracking is needed.')
 results=[]
 for name,text in prompts:
  log('REQUEST '+name)
  r=runner.send_chat_completion([{'role':'user','content':text}],max_tokens=[已隐去] if name=='32k' else 90)
  assert r['text'].strip(),name
  results.append({'case':name,**r});log('RESPONSE '+name+' '+json.dumps({'ttft':r['ttft_s'],'decode_tps':r['decode_tps'],'prompt_tokens':r['prompt_tokens'],'text':r['text']},ensure_ascii=False))
  (R/'requests.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 p.terminate()
 try:p.wait(timeout=15)
 except subprocess.TimeoutExpired:p.kill()
 (R/'timings_b.json').write_text(json.dumps(T,indent=2))
 (R/'stage_b.done').write_text(json.dumps(T));log('SUCCESS')
try:main()
except BaseException:
 log('ERROR '+traceback.format_exc());(R/'stage_b.fail').write_text(json.dumps(T))
finally:
 Path('/root/.config/rclone/rclone.conf').unlink(missing_ok=True)
 log('CONFIG_REMOVED '+str(not Path('/root/.config/rclone/rclone.conf').exists()))

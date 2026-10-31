"""Stop only our named Colab session before estimated 15-CU cap."""
import datetime,pathlib,subprocess,time,json
root=pathlib.Path('./26_Quick_Trials/06_Logs/L26.4/colab02')
# Allocation 10-22 10:47:58 EDT; own estimated 5.70 CU/h. Deadline 13:03 EDT (<14 CU).
cutoff=datetime.datetime(2026,10,22,13,3,tzinfo=datetime.timezone(datetime.timedelta(hours=-4))).timestamp()
log=root/'budget_guard.jsonl'
def write(obj):
 with log.open('a') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
write({'event':'started','cutoff':'10-22 13:03 EDT','own_rate_estimate_CU_per_h':5.70})
while time.time()<cutoff:time.sleep(min(60,max(1,cutoff-time.time())))
r=subprocess.run(['colab','--auth','oauth2','sessions'],capture_output=True,text=True,timeout=80)
write({'event':'deadline_sessions','rc':r.returncode,'contains_owned': '[l264a100]' in r.stdout,'time':datetime.datetime.now().isoformat()})
if '[l264a100]' in r.stdout:
 # Preserve small progress and failure evidence before stopping; never touch another session.
 for remote,local in [('/content/l264a100/stage_increment.json','stage_last.json'),('/content/l264a100/pilot_increment.json','pilot_last.json'),('/content/l264a100/full_increment.jsonl','full_last.jsonl')]:
  if (root/local).exists():continue
  q=subprocess.run(['colab','--auth','oauth2','download','-s','l264a100',remote,str(root/local)],capture_output=True,text=True,timeout=90)
  write({'event':'pull','remote':remote,'rc':q.returncode,'detail':q.stdout[-200:]+q.stderr[-200:]})
 q=subprocess.run(['colab','--auth','oauth2','stop','-s','l264a100'],capture_output=True,text=True,timeout=90)
 write({'event':'stop','rc':q.returncode,'detail':q.stdout[-400:]+q.stderr[-400:]})
 q=subprocess.run(['colab','--auth','oauth2','sessions'],capture_output=True,text=True,timeout=80)
 write({'event':'verify','owned_absent':'[l264a100]' not in q.stdout,'rc':q.returncode})

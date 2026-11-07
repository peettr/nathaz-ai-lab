"""Enforce segment's 20-CU ceiling conservatively against shared balance."""
import subprocess,time,json,datetime,re,pathlib
D=pathlib.Path(__file__).parent;S='ideas-convective-r2-v1seg2b-1014';CFG=D/'colab_state_cont.json';START=1396.12;THRESHOLD=1378.12

def call(a,timeout=120):
    try:
        p=subprocess.run(a,capture_output=True,text=True,timeout=timeout);return p.returncode,p.stdout+p.stderr
    except Exception as ex:return 99,repr(ex)
def cli(*a):return ['colab','--auth','oauth2','--config',str(CFG),*a]
def record(kind,**kw):
    with (D/'budget_watch.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.datetime.now().astimezone().isoformat(),'kind':kind,**kw})+'\n')
try:
    while True:
        rc,out=call(['colab','--auth','oauth2','usage']);m=re.search(r'Current balance:\s*([\d.]+)',out)
        record('usage',exit=rc,balance=float(m.group(1)) if m else None,raw=out[-400:])
        if not m:break
        state=pathlib.Path('./platform/colab-keepalive/'+S+'.json')
        if state.exists():
            st=json.loads(state.read_text());record('keepalive',status=st.get('state'),state=st)
            if st.get('state') in ('session_gone','job_ended_no_marker','log_stale','max_hours','done'):break
        if float(m.group(1))<=THRESHOLD:
            record('budget_boundary',account_delta=round(START-float(m.group(1)),2));break
        time.sleep(60)
finally:
    # Pull one fresh, unique checkpoint before stopping only our owned session.
    rc,out=call(cli('download','-s',S,'/content/r2_v1_main.jsonl',str(D/'checkpoint_budget_final.jsonl')),timeout=180);record('final_pull',exit=rc,message=out[-600:])
    rc,out=call(cli('download','-s',S,'/content/r2_v1_segment2_batch.log',str(D/'remote_batch_final.log')),timeout=180);record('log_pull',exit=rc,message=out[-600:])
    rc,out=call(cli('stop','-s',S),timeout=180);record('stop',exit=rc,message=out[-600:])
    rc,out=call(['colab','--auth','oauth2','sessions']);record('session_check',exit=rc,own_present=S in out,raw=out[-1500:])
    rc,out=call(['colab','--auth','oauth2','usage']);record('final_usage',exit=rc,raw=out[-400:])

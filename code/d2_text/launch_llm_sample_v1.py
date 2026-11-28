import pathlib, subprocess, sys
p=pathlib.Path('/content/l2631')
log=p/'d2_llm_sample_v1.log'
assert (p/'d2_sample_v1'/'samples_pre_llm.json').exists()
assert (p/'run_llm_sample.py').exists()
assert not log.exists() and not (p/'d2_sample_v1'/'samples_llm.json').exists()
wrapper=p/'llm_wrapper_v1.py'
wrapper.write_text('import subprocess,sys,pathlib\np=pathlib.Path("/content/l2631")\nr=subprocess.run([sys.executable,str(p/"run_llm_sample.py"),"--input",str(p/"d2_sample_v1"/"samples_pre_llm.json"),"--output",str(p/"d2_sample_v1"/"samples_llm.json")])\n(p/"d2_sample_v1"/"llm.exit").write_text(str(r.returncode))\n')
with log.open('x') as out:
    child=subprocess.Popen([sys.executable,'-u',str(wrapper)],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
print('LLM_SAMPLE_PID',child.pid)

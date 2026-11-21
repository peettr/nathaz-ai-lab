from pathlib import Path
import subprocess
p=Path('/content/a_stage_v2.launch');p.open('x').write('stage v2 launched\n')
cmd="cd /content && python prepare_inputs.py > /content/a_stage_v2.log 2>&1; echo $? > /content/a_stage_v2.exit; touch /content/a_stage_v2.done"
proc=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('stage_v2_pid',proc.pid)

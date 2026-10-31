from pathlib import Path
import subprocess
p=Path('/content/a_stage.launch');p.open('x').write('stage launched\n')
cmd="cd /content && python prepare_inputs.py > /content/a_stage.log 2>&1; echo $? > /content/a_stage.exit; touch /content/a_stage.done"
proc=subprocess.Popen(['bash','-lc',cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print('stage_pid',proc.pid)

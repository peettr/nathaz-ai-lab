from pathlib import Path
import subprocess
p=Path('/content/m5');p.mkdir(exist_ok=True)
assert (p/'postreview_inputs.tgz').exists()
subprocess.run(['tar','-xzf',str(p/'postreview_inputs.tgz'),'-C',str(p)],check=True)
subprocess.run(['tar','-xzf',str(p/'score_stage_archive.tgz'),'-C',str(p)],check=True)
(p/'native_obs.tgz').symlink_to('train_complete_20261027.tgz')
(p/'swiss_scores_delay4.csv').symlink_to('output/swiss_scores_delay4.csv')
(p/'swiss_predictions_delay4.parquet').symlink_to('output/swiss_predictions_delay4.parquet')
check=subprocess.run(['python','-c','import pandas, numpy, scipy, sklearn, pyarrow; print("POST_DEPS_OK")'],capture_output=True,text=True)
print(check.stdout,check.stderr,flush=True)
if check.returncode: raise RuntimeError('dependencies missing')
cmd="cd /content/m5 && (nohup bash -c 'python -u m5_postreview.py > postreview.log 2>&1; rc=$?; echo $rc > postreview.exit; touch postreview.done' </dev/null >/dev/null 2>&1 & echo POST_PID:$!)"
subprocess.run(['bash','-lc',cmd],check=True)
